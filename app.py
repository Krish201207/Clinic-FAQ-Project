import os
import re
import subprocess
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

try:
    from groq import Groq
    GROQ_IMPORT_ERROR = None
except Exception as exc:
    Groq = None
    GROQ_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

BASE_DIR = Path(__file__).resolve().parent
CPP_SOURCE = BASE_DIR / "clinic_assistant.cpp"
FAQ_FILE = BASE_DIR / "FQA.txt"
EXECUTABLE = BASE_DIR / ("ClinicAssistant.exe" if os.name == "nt" else "ClinicAssistant")
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
API_KEY = os.getenv("GROQ_API_KEY")

app = Flask(__name__, static_folder="static")
client = Groq(api_key=API_KEY) if Groq and API_KEY else None


def build_cpp():
    if not CPP_SOURCE.exists():
        raise RuntimeError("clinic_assistant.cpp is missing")
    result = subprocess.run(
        ["g++", "-std=c++17", "-O2", str(CPP_SOURCE), "-o", str(EXECUTABLE)],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode:
        raise RuntimeError(result.stderr or "C++ compilation failed")


try:
    build_cpp()
    CPP_READY, BUILD_ERROR = True, None
except Exception as exc:
    CPP_READY, BUILD_ERROR = False, str(exc)


def ask_groq(system_prompt, user_prompt):
    if client is None:
        raise RuntimeError("Groq client is not configured")
    result = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=300
    )
    answer = (result.choices[0].message.content or "").strip()
    if not answer:
        raise RuntimeError("Groq returned an empty answer")
    return answer


def generate_faq_answer(question):
    if not FAQ_FILE.exists():
        raise RuntimeError("FQA.txt is missing")
    faq_content = FAQ_FILE.read_text(encoding="utf-8")

    prompt = (
        "You are a clinic FAQ assistant. Find the single most relevant answer "
        "in the supplied FAQ and answer the patient's question using only that "
        "information. Briefly rephrase it in simple, natural English so it is "
        "not copied word for word. Preserve all facts, numbers, times, prices "
        "and conditions. Do not combine unrelated FAQ entries or add information. "
        "If the FAQ does not contain the answer, say so and direct the patient "
        "to clinic reception. Do not diagnose or give treatment advice. "
        "Return only the answer."
    )
    context = (
        f"Complete clinic FAQ:\n{faq_content}\n\n"
        f"Patient question: {question}"
    )
    return ask_groq(prompt, context)


def run_faq_engine(question):
    result = subprocess.run(
        [str(EXECUTABLE), "--machine"],
        input=question + "\nexit\n",
        capture_output=True, text=True, cwd=BASE_DIR, timeout=30
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "C++ FAQ engine failed")

    output = result.stdout
    def field(pattern):
        match = re.search(pattern, output)
        return match.group(1).strip() if match else ""

    category = field(r"Classification:\s*(ROUTINE|SENSITIVE|UNSUPPORTED)")
    if not category:
        raise ValueError(output.strip() or "C++ returned no classification")

    return {
        "category": category,
        "score": field(r"Prediction score:\s*([-0-9.]+)"),
        "margin": field(r"Top-two margin:\s*([-0-9.]+)"),
        "matched": field(r"Matched question:\s*(.*)"),
        "answer": field(r"Retrieved answer:\s*(.*)"),
        "retrieval": field(r"Retrieval status:\s*(STRONG|WEAK)"),
        "safety": field(r"Safety flag:\s*(EMERGENCY|SENSITIVE)")
    }


@app.get("/")
def home():
    return send_from_directory(BASE_DIR / "static", "index.html")


@app.get("/health")
def health():
    return jsonify({
        "ok": CPP_READY,
        "code_version": "groq-full-faq-v1",
        "deployed_commit": os.getenv("RENDER_GIT_COMMIT"),
        "cpp_ready": CPP_READY,
        "faq_file_ready": FAQ_FILE.exists(),
        "groq_package_installed": Groq is not None,
        "groq_import_error": GROQ_IMPORT_ERROR,
        "api_key_set": bool(API_KEY),
        "provider": "groq",
        "llm_configured": client is not None,
        "model": MODEL,
        "error": BUILD_ERROR
    })


@app.post("/ask")
def ask():
    if not CPP_READY:
        return jsonify({"error": "C++ engine is not ready: " + str(BUILD_ERROR)}), 500

    question = str((request.get_json(silent=True) or {}).get("question", "")).strip()
    if not question:
        return jsonify({"error": "Please enter a question."}), 400
    if len(question) > 500:
        return jsonify({"error": "Please keep the question under 500 characters."}), 400

    try:
        data = run_faq_engine(question)
    except subprocess.TimeoutExpired:
        return jsonify({"error": "The FAQ engine timed out. Please try again."}), 504
    except Exception as exc:
        app.logger.exception("FAQ engine failed")
        return jsonify({"error": str(exc)}), 500

    category = data["category"]
    score = float(data["score"]) if data["score"] else None

    if category == "UNSUPPORTED":
        answer = "I can only answer questions supported by this clinic's FAQ. Please contact reception."
        return jsonify({
            "classification": category, "prediction_score": score,
            "answer": answer, "generation": "not_used",
            "ai_rephrased": False, "response_source": "fixed_response"
        })

    if category == "SENSITIVE":
        if data["safety"] == "EMERGENCY":
            answer = ("This may be an emergency. Call 112 in India or go to the "
                      "nearest emergency department now. Seek immediate clinical help.")
        else:
            answer = ("This question needs human review. Please contact clinic staff "
                      "or a qualified clinician. I cannot provide diagnosis or treatment advice.")
        return jsonify({
            "classification": category, "prediction_score": score,
            "answer": answer, "generation": "fixed_safety_message",
            "ai_rephrased": False, "response_source": "fixed_safety_message"
        })

    matched, retrieved = data["matched"], data["answer"]
    try:
        # The complete FQA.txt is sent with every routine question.
        answer = generate_faq_answer(question)
        generation, source, error = "full_faq_context", "groq", None
    except Exception as exc:
        app.logger.exception("Groq answer generation failed")
        if retrieved:
            answer, generation, source = retrieved, "retrieval_fallback", "faq_original"
        else:
            answer = ("I couldn't generate an answer. Please contact clinic staff "
                      "for confirmation.")
            generation, source = "generation_failed", "fixed_escalation"
        error = str(exc)

    return jsonify({
        "classification": category,
        "prediction_score": score,
        "top_two_margin": float(data["margin"]) if data["margin"] else None,
        "matched_question": matched,
        "retrieved_answer": retrieved,
        "answer": answer,
        "generation": generation,
        "ai_rephrased": generation == "full_faq_context",
        "response_source": source,
        "generation_error": error
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)

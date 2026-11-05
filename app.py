import os
import re
import subprocess
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

try:
    from google import genai
    from google.genai import types
    GEMINI_IMPORT_ERROR = None
except Exception as exc:
    genai = None
    types = None
    GEMINI_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

BASE_DIR = Path(__file__).resolve().parent
CPP_SOURCE = BASE_DIR / "clinic_assistant.cpp"
FAQ_FILE = BASE_DIR / "FQA.txt"
EXECUTABLE = BASE_DIR / ("ClinicAssistant.exe" if os.name == "nt" else "ClinicAssistant")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
API_KEY = os.getenv("GEMINI_API_KEY")

app = Flask(__name__, static_folder="static")
client = genai.Client(api_key=API_KEY) if genai and API_KEY else None


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


def generate_answer(question):
    if client is None:
        raise RuntimeError("Gemini client is not configured")

    faq_content = ""
    if FAQ_FILE.exists():
        faq_content = FAQ_FILE.read_text(encoding="utf-8").strip()

    prompt = (
        "You are a helpful general-purpose assistant for a community clinic website. "
        "Answer the user's actual question even when it is unrelated to the clinic FAQ. "
        "For general knowledge questions, answer using your general knowledge. "
        "For questions asking about this specific clinic, treat the supplied FAQ as "
        "the authoritative source: use its facts when available, and if the FAQ does "
        "not contain the requested clinic-specific detail, clearly say that the FAQ "
        "does not specify it rather than inventing clinic information. "
        "Use concise, clear language. Do not claim to have performed real-world actions. "
        "For medical questions, do not diagnose, prescribe, or recommend a treatment; "
        "give general safety information and direct the user to a qualified clinician. "
        "For emergencies, advise contacting local emergency services immediately. "
        "Return only the answer."
    )

    context = (
        f"CLINIC FAQ (use only for clinic-specific facts):\n"
        f"{faq_content if faq_content else '[FAQ file unavailable]'}\n\n"
        f"USER QUESTION:\n{question}"
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=context,
        config=types.GenerateContentConfig(
            system_instruction=prompt,
            temperature=0.3,
            max_output_tokens=350
        )
    )
    answer = (response.text or "").strip()
    if not answer:
        raise RuntimeError("Gemini returned an empty answer")
    return answer


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
        "code_version": "gemini-general-answer-v1",
        "deployed_commit": os.getenv("RENDER_GIT_COMMIT"),
        "cpp_ready": CPP_READY,
        "faq_file_ready": FAQ_FILE.exists(),
        "gemini_package_installed": genai is not None,
        "gemini_import_error": GEMINI_IMPORT_ERROR,
        "api_key_set": bool(API_KEY),
        "provider": "google-gemini",
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

    try:
        # ROUTINE and UNSUPPORTED questions both reach Gemini.
        # The FAQ is optional context for clinic-specific questions, not a restriction
        # on what topics the assistant can answer.
        answer = generate_answer(question)
        generation, source, error = "general_generation", "gemini", None
    except Exception as exc:
        app.logger.exception("Gemini answer generation failed")
        answer = ("I'm unable to generate a response right now. Please try again "
                  "later or contact clinic reception for clinic-related questions.")
        generation, source, error = "generation_failed", "fixed_escalation", str(exc)

    return jsonify({
        "classification": category,
        "prediction_score": score,
        "answer": answer,
        "generation": generation,
        "ai_rephrased": False,
        "response_source": source,
        "generation_error": error
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)

from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path
from openai import OpenAI
import subprocess
import re
import os

BASE_DIR = Path(__file__).resolve().parent
CPP_SOURCE = BASE_DIR / "clinic_assistant.cpp"
EXECUTABLE = BASE_DIR / ("ClinicAssistant.exe" if os.name == "nt" else "ClinicAssistant")
MODEL_NAME = os.environ.get("OPENAI_MODEL", "gpt-5.5")

app = Flask(__name__, static_folder="static")
openai_client = OpenAI() if os.environ.get("OPENAI_API_KEY") else None


def build_cpp():
    if not CPP_SOURCE.exists():
        raise RuntimeError("clinic_assistant.cpp is missing")
    result = subprocess.run(
        ["g++", "-std=c++17", "-O2", str(CPP_SOURCE), "-o", str(EXECUTABLE)],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "C++ compilation failed")


try:
    build_cpp()
    CPP_READY = True
    BUILD_ERROR = ""
except Exception as exc:
    CPP_READY = False
    BUILD_ERROR = str(exc)


def generate_grounded_answer(question, matched_question=None, retrieved_answer=None,
                             mode="faq", emergency=False):
    """Generate only within the permitted route-specific safety boundary."""
    if openai_client is None:
        if mode == "sensitive":
            if emergency:
                return ("This may be an emergency. Call 112 in India or go to the nearest "
                        "emergency department now. Please seek immediate help from a clinician."), "generation_unavailable"
            return ("This question needs human review. Please contact clinic staff or a "
                    "clinician. I cannot provide a diagnosis or treatment recommendation."), "generation_unavailable"
        return ("I couldn't find a sufficiently reliable answer in the clinic FAQ. "
                "Please contact clinic staff for confirmation."), "generation_unavailable"

    if mode == "sensitive":
        instructions = (
            "You are a safety-routing response component for a community clinic, not a clinician. "
            "The user's question has been classified as SENSITIVE. Do not diagnose, interpret symptoms, "
            "recommend medicines, treatments, dosages, or home remedies. Do not claim that the user is "
            "safe. Respond briefly and empathetically, explain that a clinic staff member or qualified "
            "clinician must review the question, and direct the user to contact the clinic. "
            "If the emergency flag is true, clearly tell the user to call 112 in India or go to the "
            "nearest emergency department now. Do not delay emergency care with follow-up questions."
        )
        context = (f"User question:\n{question}\n\n"
                   f"Emergency flag: {'true' if emergency else 'false'}\n"
                   "Generate a safe escalation response. Do not provide medical advice.")
    else:
        instructions = (
            "You are the response-writing component of a community clinic FAQ assistant. "
            "The FAQ retrieval system marked its closest match as WEAK, so the candidate may be "
            "irrelevant. First determine whether the supplied FAQ entry directly and explicitly "
            "contains enough information to answer the user's question. If it does, answer using "
            "only that entry. If it does not, say the clinic FAQ does not contain enough information "
            "and direct the user to clinic staff. Never guess or use outside knowledge. Do not use "
            "outside medical knowledge, diagnose, recommend medicines or treatments, or invent clinic "
            "policies, timings, prices, or services. Keep the answer concise. Never claim to be a doctor."
        )
        context = (
            f"User question:\n{question}\n\n"
            f"Closest FAQ question (weak match; may be irrelevant):\n{matched_question or 'No candidate found'}\n\n"
            f"Candidate FAQ answer:\n{retrieved_answer or 'No answer available'}\n\n"
            "Only answer if this entry directly supports the answer; otherwise escalate to clinic staff."
        )

    response = openai_client.responses.create(
        model=MODEL_NAME,
        instructions=instructions,
        input=context,
        store=False
    )
    generated = (response.output_text or "").strip()
    if not generated:
        raise RuntimeError("The model returned an empty response")
    return generated, ("rag_sensitive_escalation" if mode == "sensitive" else "rag_weak_match")


@app.get("/")
def home():
    return send_from_directory(BASE_DIR / "static", "index.html")


@app.get("/health")
def health():
    return jsonify({
        "ok": CPP_READY,
        "cpp_ready": CPP_READY,
        "llm_configured": openai_client is not None,
        "model": MODEL_NAME if openai_client is not None else None,
        "error": BUILD_ERROR if not CPP_READY else None
    })


@app.post("/ask")
def ask():
    if not CPP_READY:
        return jsonify({"error": "The C++ engine is not ready: " + BUILD_ERROR}), 500

    data = request.get_json(silent=True) or {}
    question = str(data.get("question", "")).strip()
    if not question:
        return jsonify({"error": "Please enter a question."}), 400
    if len(question) > 500:
        return jsonify({"error": "Please keep the question under 500 characters."}), 400

    try:
        result = subprocess.run(
            [str(EXECUTABLE)],
            input=question + "\nexit\n",
            capture_output=True,
            text=True,
            cwd=BASE_DIR,
            timeout=30
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "The FAQ engine took too long to respond. Try again."}), 504

    if result.returncode != 0:
        message = result.stderr.strip() or "The C++ FAQ engine failed. Check its data files."
        return jsonify({"error": message}), 500

    output = result.stdout
    category_match = re.search(
        r"Classification:\s*(ROUTINE|SENSITIVE|UNSUPPORTED)", output
    )
    matched_match = re.search(r"Matched question:\s*(.*)", output)
    retrieved_match = re.search(r"Retrieved answer:\s*(.*)", output)
    status_match = re.search(r"Retrieval status:\s*(STRONG|WEAK)", output)
    safety_match = re.search(r"Safety flag:\s*(EMERGENCY|SENSITIVE)", output)
    answer_match = re.search(r"Assistant:\s*(.*?)(?=\n(?:Matched question:|Retrieved answer:|Retrieval status:|Safety flag:)|\n\s*$)", output, re.S)

    if not category_match:
        clean = output.strip()
        return jsonify({
            "error": clean or "No classification was produced. Check the embedding and weight files."
        }), 422

    category = category_match.group(1)
    matched_question = matched_match.group(1).strip() if matched_match else None
    retrieved_answer = retrieved_match.group(1).strip() if retrieved_match else ""

                                                              
    if category == "UNSUPPORTED":
        return jsonify({
            "classification": category,
            "answer": "I can only answer questions supported by this clinic's FAQ. Please contact reception for this request.",
            "generation": "not_used"
        })

                                                                                      
                                                                                            
    if category == "SENSITIVE":
        emergency = bool(safety_match and safety_match.group(1) == "EMERGENCY")
        try:
            final_answer, generation_status = generate_grounded_answer(
                question, mode="sensitive", emergency=emergency
            )
        except Exception:
            app.logger.exception("Sensitive-question response generation failed")
            if emergency:
                final_answer = ("This may be an emergency. Call 112 in India or go to the nearest "
                                "emergency department now. Please seek immediate help from a clinician.")
            else:
                final_answer = ("This question needs human review. Please contact clinic staff or a "
                                "clinician. I cannot provide a diagnosis or treatment recommendation.")
            generation_status = "safe_escalation_fallback"
        return jsonify({
            "classification": category,
            "answer": final_answer,
            "generation": generation_status
        })

                                                                    
                                                                                           
    is_strong = bool(status_match and status_match.group(1) == "STRONG")
    if is_strong and matched_question and retrieved_answer:
        try:
            final_answer, generation_status = generate_grounded_answer(
                question, matched_question, retrieved_answer, mode="faq"
            )
        except Exception:
            app.logger.exception("LLM answer generation failed")
            final_answer = retrieved_answer
            generation_status = "retrieval_fallback"
    else:
        try:
            final_answer, generation_status = generate_grounded_answer(
                question, matched_question, retrieved_answer, mode="weak"
            )
        except Exception:
            app.logger.exception("Weak-match response generation failed")
            final_answer = ("I couldn't find a sufficiently reliable answer in the clinic FAQ. "
                            "Please contact clinic staff for confirmation.")
            generation_status = "weak_match_escalation_fallback"

    return jsonify({
        "classification": category,
        "matched_question": matched_question,
        "retrieved_answer": retrieved_answer or None,
        "answer": final_answer,
        "generation": generation_status
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )

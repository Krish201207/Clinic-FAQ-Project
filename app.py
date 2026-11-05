import os
import re
import subprocess
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import threading
import time

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
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
API_KEY = os.getenv("GEMINI_API_KEY")
CACHE_TTL_SECONDS = max(600, int(os.getenv("GEMINI_CACHE_TTL_SECONDS", "3600")))

app = Flask(__name__, static_folder="static")
client = genai.Client(api_key=API_KEY) if genai and API_KEY else None

FAQ_SYSTEM_INSTRUCTION = (
    "You are a community clinic FAQ assistant. The complete clinic FAQ is "
    "provided in your cached context. Answer patient questions using only "
    "that information. Understand paraphrases and different wording; do not "
    "require the patient to use the FAQ's exact wording. Give a concise, "
    "natural answer and preserve all facts, numbers, times, prices and "
    "conditions. Do not invent or assume details. If the FAQ does not contain "
    "the answer, say that the information is unavailable and direct the "
    "patient to clinic reception. Never diagnose, prescribe, or recommend "
    "treatment. Return only the answer."
)

_faq_cache = None
_faq_cache_created_at = 0.0
_faq_cache_lock = threading.Lock()
_faq_cache_error = None


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


def get_faq_cache():
    global _faq_cache, _faq_cache_created_at, _faq_cache_error

    if client is None:
        raise RuntimeError("Gemini client is not configured")
    if not FAQ_FILE.exists():
        raise RuntimeError("FQA.txt is missing")

    # Create the remote cache once per running server process and reuse it.
    with _faq_cache_lock:
        still_valid = (
            _faq_cache is not None
            and time.monotonic() - _faq_cache_created_at < CACHE_TTL_SECONDS - 60
        )
        if still_valid:
            return _faq_cache

        faq_content = FAQ_FILE.read_text(encoding="utf-8").strip()
        if not faq_content:
            raise RuntimeError("FQA.txt is empty")

        try:
            cached = client.caches.create(
                model=MODEL,
                config=types.CreateCachedContentConfig(
                    contents=[
                        types.Content(
                            role="user",
                            parts=[types.Part.from_text(text=faq_content)]
                        )
                    ],
                    system_instruction=FAQ_SYSTEM_INSTRUCTION,
                    ttl=f"{CACHE_TTL_SECONDS}s",
                    display_name="community-clinic-faq"
                )
            )
            _faq_cache = cached
            _faq_cache_created_at = time.monotonic()
            _faq_cache_error = None
            app.logger.info("Created Gemini FAQ context cache: %s", cached.name)
            return _faq_cache
        except Exception as exc:
            _faq_cache_error = f"{type(exc).__name__}: {exc}"
            raise RuntimeError(f"Could not create Gemini FAQ cache: {_faq_cache_error}") from exc


def generate_faq_answer(question):
    cache = get_faq_cache()
    result = client.models.generate_content(
        model=MODEL,
        contents=question,
        config=types.GenerateContentConfig(
            cached_content=cache.name,
            temperature=0.2,
            max_output_tokens=250
        )
    )
    answer = (result.text or "").strip()
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
        "code_version": "gemini-cached-faq-v1",
        "deployed_commit": os.getenv("RENDER_GIT_COMMIT"),
        "cpp_ready": CPP_READY,
        "faq_file_ready": FAQ_FILE.exists(),
        "gemini_package_installed": genai is not None,
        "gemini_import_error": GEMINI_IMPORT_ERROR,
        "api_key_set": bool(API_KEY),
        "provider": "google-gemini",
        "llm_configured": client is not None,
        "model": MODEL,
        "faq_cache_created": _faq_cache is not None,
        "faq_cache_error": _faq_cache_error,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
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

    try:
        # The FAQ is cached remotely once per server process. Each request sends
        # only the patient's question to Gemini.
        answer = generate_faq_answer(question)
        generation, source, error = "cached_faq_generation", "gemini", None
    except Exception as exc:
        app.logger.exception("Gemini answer generation failed")
        answer = ("I can't access the clinic FAQ right now. Please contact "
                  "clinic reception for assistance.")
        generation, source, error = "generation_failed", "fixed_escalation", str(exc)

    return jsonify({
        "classification": category,
        "prediction_score": score,
        "answer": answer,
        "generation": generation,
        "ai_rephrased": generation == "cached_faq_generation",
        "response_source": source,
        "generation_error": error
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)

from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path
import subprocess
import re
import os

BASE_DIR = Path(__file__).resolve().parent
CPP_SOURCE = BASE_DIR / "clinic_assistant.cpp"
EXECUTABLE = BASE_DIR / "ClinicAssistant"

app = Flask(__name__, static_folder="static")


def build_cpp():
    """Compile the existing C++ FAQ engine for the deployment machine."""
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


@app.get("/")
def home():
    return send_from_directory(BASE_DIR / "static", "index.html")


@app.get("/health")
def health():
    return jsonify({"ok": CPP_READY, "cpp_ready": CPP_READY,
                    "error": BUILD_ERROR if not CPP_READY else None})


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

    # The C++ program reads one question, then 'exit' to finish this request.
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
    category_match = re.search(r"Classification:\s*(ROUTINE|SENSITIVE|UNSUPPORTED)", output)
    score_match = re.search(r"Prediction score:\s*([0-9.]+)", output)
    answer_match = re.search(r"Assistant:\s*(.*?)(?=\nMatched question:|\n\s*$)", output, re.S)
    matched_match = re.search(r"Matched question:\s*(.*)", output)

    if not category_match:
        # Usually indicates missing/mismatched embedding or model files.
        clean = output.strip()
        return jsonify({"error": clean or "No classification was produced. Check the embedding and weight files."}), 422

    category = category_match.group(1)
    answer = answer_match.group(1).strip() if answer_match else ""
    matched = matched_match.group(1).strip() if matched_match else None
    score = float(score_match.group(1)) if score_match else None

    return jsonify({
        "classification": category,
        "prediction_score": score,
        "matched_question": matched,
        "answer": answer
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)

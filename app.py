import os
import sys
from pathlib import Path

# Install with: pip install -U google-genai
try:
    from google import genai
    from google.genai import types
except Exception as exc:
    print("[FAIL] Cannot import Gemini SDK.")
    print(f"Error: {type(exc).__name__}: {exc}")
    print("Run: pip install -U google-genai")
    raise SystemExit(1)

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
FAQ_PATH = Path(__file__).resolve().parent / "FQA.txt"

print("=== GEMINI QUESTION / ANSWER TEST ===")
print(f"Model: {MODEL}")
print(f"FAQ file: {FAQ_PATH}")
print(f"FAQ exists: {FAQ_PATH.is_file()}")
print(f"API key configured: {bool(API_KEY)}")

if not API_KEY:
    print("\n[FAIL] GEMINI_API_KEY is not set.")
    print('PowerShell: $env:GEMINI_API_KEY="YOUR_API_KEY"')
    raise SystemExit(1)

if not FAQ_PATH.is_file():
    print("\n[FAIL] FQA.txt is not in the same folder as this script.")
    raise SystemExit(1)

faq = FAQ_PATH.read_text(encoding="utf-8").strip()
if not faq:
    print("\n[FAIL] FQA.txt is empty.")
    raise SystemExit(1)

print(f"FAQ size: {len(faq)} characters")
question = " ".join(sys.argv[1:]).strip()
if not question:
    question = input("\nEnter a patient question: ").strip()

if not question:
    print("[FAIL] No question entered.")
    raise SystemExit(1)

client = genai.Client(api_key=API_KEY)

prompt = f"""
You are a community clinic FAQ assistant.
Answer the patient's question using ONLY the clinic FAQ below.
Understand different wording and paraphrases; do not require an exact FAQ question.
Give a concise, natural answer. Preserve all facts, numbers, times, prices,
and conditions. Do not invent information.
If the FAQ does not contain the answer, say that the FAQ does not provide it
and direct the patient to clinic reception.
Never diagnose, prescribe, or recommend treatment.

CLINIC FAQ:
{faq}

PATIENT QUESTION:
{question}

Return only the answer.
"""

print("\n--- Sending question and FAQ to Gemini ---")
try:
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=250
        )
    )
    answer = (response.text or "").strip()
    if not answer:
        print("[FAIL] Gemini request succeeded but returned no text.")
        print("Check response candidates or safety blocking in the API response.")
        raise SystemExit(2)

    print("\n[PASS] Gemini API request succeeded.")
    print("\nPatient question:")
    print(question)
    print("\nGemini answer:")
    print(answer)
    print("\nThis test uses ordinary generation, not context caching.")
    print("The complete FAQ is included in this request.")
except Exception as exc:
    print("\n[FAIL] Gemini API request failed.")
    print(f"Error type: {type(exc).__name__}")
    print(f"Error details: {exc}")
    print("\nCommon causes:")
    print("- Invalid or missing GEMINI_API_KEY")
    print("- Model name unavailable to this API key/project")
    print("- API not enabled, quota/rate limit, or billing restriction")
    print("- Network or temporary Google API error")
    raise SystemExit(3)

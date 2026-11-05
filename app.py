import os
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except Exception as exc:
    print("[FAIL] Gemini SDK import failed.")
    print(f"       {type(exc).__name__}: {exc}")
    print("       Install it with: pip install -U google-genai")
    raise SystemExit(1)

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
TTL = os.getenv("GEMINI_CACHE_TTL_SECONDS", "3600").strip()
FAQ_PATH = Path(__file__).resolve().parent / "FQA.txt"

print("=== GEMINI CONFIGURATION TEST ===")
print(f"Model: {MODEL}")
print(f"FAQ file: {FAQ_PATH}")
print(f"FAQ exists: {FAQ_PATH.is_file()}")
print(f"API key configured: {bool(API_KEY)}")

if not API_KEY:
    print("\n[FAIL] GEMINI_API_KEY is missing.")
    print("Set it in your terminal or Render environment variables.")
    raise SystemExit(1)

if not FAQ_PATH.is_file():
    print("\n[FAIL] FQA.txt was not found beside this script.")
    raise SystemExit(1)

faq = FAQ_PATH.read_text(encoding="utf-8").strip()
if not faq:
    print("\n[FAIL] FQA.txt is empty.")
    raise SystemExit(1)

print(f"FAQ characters: {len(faq)}")
client = genai.Client(api_key=API_KEY)

print("\n--- TEST 1: Basic Gemini API access ---")
try:
    response = client.models.generate_content(
        model=MODEL,
        contents="Reply with exactly: GEMINI_CONNECTION_OK",
        config=types.GenerateContentConfig(max_output_tokens=20, temperature=0)
    )
    print("[PASS] Gemini generated a response.")
    print(f"       Response: {(response.text or '').strip()[:200]}")
except Exception as exc:
    print("[FAIL] Basic Gemini request failed.")
    print(f"       {type(exc).__name__}: {exc}")
    print("\nCache test skipped because basic API access failed.")
    raise SystemExit(2)

print("\n--- TEST 2: Explicit FAQ context cache ---")
try:
    ttl_seconds = int(TTL)
    if ttl_seconds < 600:
        raise ValueError("GEMINI_CACHE_TTL_SECONDS must be at least 600 seconds.")

    cache = client.caches.create(
        model=MODEL,
        config=types.CreateCachedContentConfig(
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=faq)]
                )
            ],
            system_instruction=(
                "You are a clinic FAQ assistant. Answer only from the supplied "
                "FAQ. If the answer is absent, say so. Do not invent facts or "
                "give diagnosis or treatment advice."
            ),
            ttl=f"{ttl_seconds}s",
            display_name="clinic-faq-diagnostic"
        )
    )
    print("[PASS] FAQ context cache created.")
    print(f"       Cache name: {cache.name}")

    print("\n--- TEST 3: Generate using cached FAQ ---")
    answer = client.models.generate_content(
        model=MODEL,
        contents="What are the clinic's opening hours?",
        config=types.GenerateContentConfig(
            cached_content=cache.name,
            temperature=0.2,
            max_output_tokens=120
        )
    )
    print("[PASS] Cached-context generation succeeded.")
    print(f"       Answer: {(answer.text or '').strip()[:500]}")

    print("\n--- TEST 4: Clean up test cache ---")
    try:
        client.caches.delete(name=cache.name)
        print("[PASS] Temporary diagnostic cache deleted.")
    except Exception as exc:
        print("[WARN] Could not delete temporary cache automatically.")
        print(f"       {type(exc).__name__}: {exc}")
        print("       It should expire according to its TTL.")

    print("\nRESULT: Gemini API, cache creation, and cached generation all passed.")

except Exception as exc:
    print("[FAIL] Explicit context caching or cached generation failed.")
    print(f"       {type(exc).__name__}: {exc}")
    print("\nInterpretation:")
    print("- Check whether this model supports explicit context caching.")
    print("- Check whether your API project/tier has cache access.")
    print("- Check cache minimum-token requirements and the FAQ size.")
    print("- Check the full error above; it usually identifies the cause.")
    raise SystemExit(3)

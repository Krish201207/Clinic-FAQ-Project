#!/usr/bin/env python3
from pathlib import Path
import py_compile
import re
import shutil
import sys

APP_FILE = Path(__file__).resolve().parent / "app.py"

FIXED_FUNCTION = (
    "def _extract_visit_reason(text):\n"
    "    q = text.strip()\n"
    "    match = re.search(\n"
    "        r'\\b(?:because|reason(?: is)?|for|about|regarding)\\s+(.+)',\n"
    "        q,\n"
    "        re.IGNORECASE\n"
    "    )\n"
    "    if match:\n"
    "        return match.group(1).strip(\" \\t\\r\\n.,;:!?\")[:300]\n"
    "    return \"\"\n\n\n"
)

def main():
    if not APP_FILE.is_file():
        print("ERROR: app.py was not found.")
        print("Put fix_app.py in the same folder as your Clinic-FAQ-Project app.py.")
        sys.exit(1)

    source = APP_FILE.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(?ms)^def _extract_visit_reason[(]text[)]:.*?(?=^def _parse_chat_time[(]text[)]:)"
    )
    updated, count = pattern.subn(lambda _: FIXED_FUNCTION, source, count=1)

    if count != 1:
        print("ERROR: The expected broken function was not found. No changes made.")
        sys.exit(1)

    backup = APP_FILE.with_name("app.py.backup")
    if backup.exists():
        backup = APP_FILE.with_name("app.py.backup2")
    shutil.copy2(APP_FILE, backup)
    APP_FILE.write_text(updated, encoding="utf-8")

    try:
        py_compile.compile(str(APP_FILE), doraise=True)
    except py_compile.PyCompileError as exc:
        shutil.copy2(backup, APP_FILE)
        print("ERROR: Syntax check failed; original app.py was restored.")
        print(exc)
        sys.exit(1)

    print("SUCCESS: app.py was repaired and passed Python syntax validation.")
    print(f"Original backup: {backup.name}")
    print("Commit and push app.py to GitHub, then redeploy on Render.")

if __name__ == "__main__":
    main()

"""Static security checks for Kharidino source code.

Run with: python security_audit.py
Returns non-zero when a high-risk pattern is found.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGETS = [ROOT / "app.py", ROOT / "kharidino_ai.py", ROOT / "run_kharidino.py", ROOT / "mobile_app" / "api" / "mobile_api.py"]
PATTERNS = {
    "known fallback SECRET_KEY": re.compile(r"change-this-secret-key"),
    "hard-coded OpenAI key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "shell command execution": re.compile(r"\b(os\.system|subprocess\.(run|Popen|call)|eval\(|exec\()"),
    "unsafe template rendering": re.compile(r"render_template_string\s*\("),
}


def main() -> int:
    findings = []
    for path in TARGETS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append((path.relative_to(ROOT), line, name))

    if findings:
        print("SECURITY FINDINGS")
        for path, line, name in findings:
            print(f"- {path}:{line}: {name}")
        return 1

    print("SECURITY AUDIT: no high-risk static patterns found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

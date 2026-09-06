"""Static security checks for Kharidino source code.

Run with: python security_audit.py
Returns non-zero when a high-risk pattern is found in application/runtime code.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", "node_modules"}

# These files contain security-test sentinels/allowlists by design. The audit
# must inspect application code, not report the detector's own signatures.
APPLICATION_FILES = {
    Path("app.py"),
    Path("run_kharidino.py"),
    Path("mobile_app/api/mobile_api.py"),
}

PATTERNS = {
    "known fallback SECRET_KEY": re.compile(r"change-this-secret-key"),
    "hard-coded bootstrap admin password": re.compile(r"admin12345"),
    "hard-coded OpenAI key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "private key material": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "shell command execution": re.compile(r"\b(os\.system|subprocess\.(run|Popen|call)|eval\(|exec\()"),
    "unsafe template rendering": re.compile(r"render_template_string\s*\("),
    "Flask debug explicitly enabled": re.compile(r"\bdebug\s*=\s*True\b"),
}


def iter_source_files():
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        relative = path.relative_to(ROOT)
        if relative not in APPLICATION_FILES:
            continue
        yield path


def main() -> int:
    findings = []
    for path in iter_source_files():
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

"""Static security checks for Kharidino source code.

Run with: python security_audit.py
The audit intentionally scans runtime Python code, excluding tests and this
checker itself, so new modules cannot silently bypass the security baseline.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", "node_modules", "tests"}

PATTERNS = {
    "hard-coded bootstrap admin password": re.compile(r"admin12345"),
    "hard-coded OpenAI key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "private key material": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "shell command execution": re.compile(r"\b(?:os\.system|subprocess\.(?:run|Popen|call)|eval|exec)\s*\("),
    "unsafe template rendering": re.compile(r"\brender_template_string\s*\("),
    "Flask debug explicitly enabled": re.compile(r"\bdebug\s*=\s*True\b"),
}

# Known-safe security implementation constants are excluded from secret checks.
ALLOWED_SECURITY_FILES = {Path("security_hardening.py")}


def iter_source_files():
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name == "security_audit.py":
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

    print("SECURITY AUDIT: runtime source scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

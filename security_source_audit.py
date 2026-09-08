"""Static security checks for runtime Python and Jinja templates.

The audit is intentionally conservative: it blocks high-risk server-side
rendering/XSS primitives instead of trying to prove that arbitrary HTML is safe.
Normal Jinja interpolation remains allowed because Flask/Jinja auto-escapes HTML
templates by default.
"""
from __future__ import annotations

from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent
EXCLUDED_DIRS = {".git", "venv", ".venv", "__pycache__", "node_modules"}

PYTHON_PATTERNS = {
    "render_template_string": re.compile(r"\brender_template_string\s*\("),
    "Markup(user_input)": re.compile(r"\bMarkup\s*\([^\n]*(?:request|session|form|args|json|input)", re.I),
    "eval/exec": re.compile(r"\b(?:eval|exec)\s*\("),
}

TEMPLATE_PATTERNS = {
    "Jinja safe filter": re.compile(r"\|\s*safe\b"),
    "autoescape disabled": re.compile(r"\{%-?\s*autoescape\s+false\b", re.I),
    "javascript URL": re.compile(r"(?:href|src|action)\s*=\s*['\"]\s*javascript:", re.I),
}


def _iter_files(suffixes: tuple[str, ...]):
    for path in BASE_DIR.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        yield path


def audit() -> list[str]:
    findings: list[str] = []
    for path in _iter_files((".py",)):
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in PYTHON_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(BASE_DIR)}: {name}")

    for path in _iter_files((".html", ".jinja", ".jinja2")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in TEMPLATE_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(BASE_DIR)}: {name}")
    return findings


def main() -> int:
    findings = audit()
    if findings:
        print("SECURITY SOURCE AUDIT: FAILED")
        for finding in findings:
            print(f" - {finding}")
        return 1
    print("SECURITY SOURCE AUDIT: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

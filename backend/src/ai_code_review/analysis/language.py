"""Initial supported languages have installed grammars, not runtime downloads."""

from pathlib import Path

LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
}


def detect_language(path: str) -> str | None:
    return LANGUAGES.get(Path(path).suffix.lower())

import tempfile
from pathlib import Path

_LANGUAGE_ALIASES = {
    "c#": "csharp",
    "csharp": "csharp",
    "cpp": "cpp",
    "c++": "cpp",
    "cs": "csharp",
    "css": "css",
    "go": "go",
    "golang": "go",
    "html": "html",
    "java": "java",
    "javascript": "javascript",
    "js": "javascript",
    "json": "json",
    "md": "markdown",
    "markdown": "markdown",
    "python": "python",
    "py": "python",
    "rb": "ruby",
    "ruby": "ruby",
    "rs": "rust",
    "rust": "rust",
    "toml": "toml",
    "ts": "typescript",
    "tsx": "tsx",
    "typescript": "typescript",
    "yaml": "yaml",
    "yml": "yaml",
    "c": "c",
}

_EXTENSION_LANGUAGE_MAP = {
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".cxx": "cpp",
    ".go": "go",
    ".h": "c",
    ".hh": "cpp",
    ".hpp": "cpp",
    ".htm": "html",
    ".html": "html",
    ".java": "java",
    ".js": "javascript",
    ".json": "json",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".md": "markdown",
    ".markdown": "markdown",
    ".py": "python",
    ".rb": "ruby",
    ".rs": "rust",
    ".scss": "css",
    ".css": "css",
    ".toml": "toml",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".yaml": "yaml",
    ".yml": "yaml",
}

_LANGUAGE_DEFAULT_EXTENSIONS = {
    "c": ".c",
    "cpp": ".cpp",
    "csharp": ".cs",
    "css": ".css",
    "go": ".go",
    "html": ".html",
    "java": ".java",
    "javascript": ".js",
    "json": ".json",
    "markdown": ".md",
    "python": ".py",
    "ruby": ".rb",
    "rust": ".rs",
    "toml": ".toml",
    "tsx": ".tsx",
    "typescript": ".ts",
    "yaml": ".yml",
}

_SUPPORTED_LANGUAGES = set(_LANGUAGE_DEFAULT_EXTENSIONS)


def normalize_language(language: str) -> str:
    normalized = language.strip().lower()
    resolved = _LANGUAGE_ALIASES.get(normalized, normalized)
    if resolved not in _SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language '{language}'. Supported: {sorted(_SUPPORTED_LANGUAGES)}")
    return resolved


def detect_language_from_path(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in _EXTENSION_LANGUAGE_MAP:
        return _EXTENSION_LANGUAGE_MAP[suffix]
    raise ValueError(f"Unsupported file extension: {suffix}")


def resolve_language(language: str | None, file_path: Path | None) -> str:
    if language:
        return normalize_language(language)
    if file_path:
        return detect_language_from_path(file_path)
    raise ValueError("Language must be provided when no file path is available.")


def write_temp_code_file(source: str, language: str) -> Path:
    suffix = _LANGUAGE_DEFAULT_EXTENSIONS.get(language, ".txt")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(source.encode("utf-8"))
        temp_file.flush()
        return Path(temp_file.name)

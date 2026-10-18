#!/usr/bin/env python3
"""
vault_lint.py - health checks for the LLM Wiki vault.

Checks folder scaffold, markdown links, wikilinks, duplicate basenames, and
source hygiene. No external dependencies.
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path


# VAULT_ROOT env wins; default is the kit's own ./vault (one level above scripts/).
VAULT_ROOT = Path(os.environ.get("VAULT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()
REQUIRED_DIRS = [
    "00-inbox",
    "01-projects",
    "02-areas",
    "03-resources",
    "04-archive",
    "05-daily",
    "06-maps",
    "_raw",
    "_outputs",
    "_meta",
]
REQUIRED_FILES = ["README.md"]
SKIP_PARTS = {".obsidian", ".trash", "templates", "scripts"}
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
MD_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


@dataclass
class Issue:
    severity: str
    path: str
    message: str


def iter_markdown():
    for path in VAULT_ROOT.rglob("*.md"):
        rel = path.relative_to(VAULT_ROOT)
        if any(part in SKIP_PARTS for part in rel.parts):
            continue
        yield path


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def build_note_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for path in iter_markdown():
        rel = path.relative_to(VAULT_ROOT)
        keys = {path.stem.lower(), str(rel.with_suffix("")).lower(), str(rel).lower()}
        for key in keys:
            index.setdefault(key, []).append(path)
    return index


def resolve_wikilink(target: str, index: dict[str, list[Path]]) -> bool:
    key = target.strip().replace("\\", "/").removesuffix(".md").lower()
    if key in index:
        return True
    basename = Path(key).name
    return basename in index


def lint_structure(issues: list[Issue]) -> None:
    for dirname in REQUIRED_DIRS:
        if not (VAULT_ROOT / dirname).is_dir():
            issues.append(Issue("error", dirname, "Required directory is missing"))
    for filename in REQUIRED_FILES:
        if not (VAULT_ROOT / filename).is_file():
            issues.append(Issue("error", filename, "Required file is missing"))


def lint_duplicate_basenames(issues: list[Issue]) -> None:
    seen: dict[str, list[str]] = {}
    for path in iter_markdown():
        rel = path.relative_to(VAULT_ROOT)
        if rel.parts[0] == "_raw" or path.name.lower() == "readme.md":
            continue
        seen.setdefault(path.stem.lower(), []).append(str(path.relative_to(VAULT_ROOT)))
    for name, paths in seen.items():
        if len(paths) > 1:
            issues.append(Issue("warn", paths[0], f"Duplicate basename '{name}' appears in: {', '.join(paths)}"))


def lint_links(issues: list[Issue]) -> None:
    index = build_note_index()
    for path in iter_markdown():
        rel = path.relative_to(VAULT_ROOT)
        if rel.parts[0] == "_raw":
            continue
        text = read(path)
        for target in WIKILINK_RE.findall(text):
            if not resolve_wikilink(target, index):
                issues.append(Issue("error", str(rel), f"Broken wikilink: [[{target}]]"))
        for raw_target in MD_LINK_RE.findall(text):
            if raw_target.startswith(("http://", "https://", "mailto:")):
                continue
            target = raw_target.split("#", 1)[0]
            if not target or target.startswith("<"):
                continue
            decoded = target.replace("%20", " ")
            resolved = (path.parent / decoded).resolve()
            if not str(resolved).startswith(str(VAULT_ROOT.resolve())):
                issues.append(Issue("error", str(rel), f"Markdown link escapes vault: {raw_target}"))
            elif not resolved.exists():
                issues.append(Issue("error", str(rel), f"Broken Markdown link: {raw_target}"))


def lint_source_hygiene(issues: list[Issue]) -> None:
    raw_files = list((VAULT_ROOT / "_raw").rglob("*.md")) if (VAULT_ROOT / "_raw").exists() else []
    if not raw_files:
        issues.append(Issue("warn", "_raw", "No raw source Markdown files found"))
    compiled_files = [
        p for p in iter_markdown()
        if p.relative_to(VAULT_ROOT).parts[0] in {"03-resources", "06-maps", "01-projects", "02-areas"}
    ]
    for path in compiled_files:
        text = read(path)
        if "# " not in text:
            issues.append(Issue("warn", str(path.relative_to(VAULT_ROOT)), "Compiled note has no H1 heading"))
        if "## Sources" not in text and path.relative_to(VAULT_ROOT).parts[0] in {"03-resources", "06-maps"}:
            issues.append(Issue("warn", str(path.relative_to(VAULT_ROOT)), "Compiled map/resource has no Sources section"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint a Markdown knowledge vault")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on warnings as well as errors")
    args = parser.parse_args()

    issues: list[Issue] = []
    lint_structure(issues)
    lint_duplicate_basenames(issues)
    lint_links(issues)
    lint_source_hygiene(issues)

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warn"]

    print(f"Vault: {VAULT_ROOT}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")
    for issue in issues:
        print(f"{issue.severity.upper():5} {issue.path}: {issue.message}")

    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

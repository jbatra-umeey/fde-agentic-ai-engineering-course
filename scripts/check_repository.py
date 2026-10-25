"""Basic publication hygiene and local Markdown link checks, not a security audit."""

import re
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    failures, diagrams = [], 0
    for path in sorted(root.rglob("*.md")):
        if any(p.startswith(".") for p in path.relative_to(root).parts):
            continue
        content = path.read_text()
        diagrams += content.count("```mermaid")
        for target in re.findall(r"\]\(([^)]+)\)", content):
            if target.startswith(("https://", "http://", "#", "mailto:")):
                continue
            target = target.split("#")[0].split("?")[0]
            if not (path.parent / target).exists():
                failures.append(f"Broken link: {path.relative_to(root)} -> {target}")
    assert len(list((root / "docs/modules").glob("*.md"))) == 10
    assert len(list((root / "examples").glob("*/main.py"))) == 10
    secret_patterns = [
        r"AKIA[A-Z0-9]{16}",
        r"ghp_[A-Za-z0-9]{36}",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    ]
    for directory in ["apps", "packages", "scripts", "docs", "course", "tests", ".github"]:
        for path in (root / directory).rglob("*"):
            if path.suffix not in {".py", ".md", ".yml", ".yaml", ".json"}:
                continue
            content = path.read_text()
            if any(re.search(pattern, content) for pattern in secret_patterns):
                failures.append(f"Potential credential: {path.relative_to(root)}")
    if failures:
        raise SystemExit("\n".join(failures))
    print(
        f"10 modules, 10 examples, {diagrams} Mermaid blocks; Markdown links and basic credential-pattern checks passed."
    )


if __name__ == "__main__":
    main()

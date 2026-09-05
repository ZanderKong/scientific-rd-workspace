"""Reject removed v0.2 runtime storage references outside migration history."""

from __future__ import annotations

from pathlib import Path

FORBIDDEN = ("DataPayload", "data_payloads", "payload_kind")
ROOT = Path(__file__).resolve().parents[2]
CHECK_PATHS = (
    ROOT / "api" / "app",
    ROOT / "api" / "scripts",
    ROOT / "web" / "src",
    ROOT / ".github",
)


def main() -> None:
    violations: list[str] = []
    for path in CHECK_PATHS:
        for file in path.rglob("*"):
            if not file.is_file() or file.suffix not in {
                ".py",
                ".ts",
                ".tsx",
                ".yml",
                ".yaml",
                ".sh",
            }:
                continue
            if file == Path(__file__):
                continue
            text = file.read_text(encoding="utf-8")
            for token in FORBIDDEN:
                if token in text:
                    violations.append(f"{file.relative_to(ROOT)}: {token}")
    if violations:
        raise AssertionError("removed v0.2 runtime reference(s):\n" + "\n".join(violations))
    print("No removed v0.2 runtime references found")


if __name__ == "__main__":
    main()

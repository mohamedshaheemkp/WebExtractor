from __future__ import annotations

from pathlib import Path


def build_tree(
    directory: Path,
) -> list[str]:

    lines = []

    for path in sorted(
        directory.rglob("*")
    ):

        level = len(path.relative_to(directory).parts)

        indent = "    " * (level - 1)

        lines.append(
            f"{indent}{path.name}"
        )

    return lines


def write_tree(
    directory: Path,
) -> None:

    tree = build_tree(directory)

    with (directory / "tree.txt").open(
        "w",
        encoding="utf-8",
    ) as f:

        f.write("\n".join(tree))
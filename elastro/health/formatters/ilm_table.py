"""Table formatter for stuck ILM indices."""

from __future__ import annotations

from typing import List

from elastro.health.ilm_status import StuckIlmIndex


def format_stuck_ilm_table(indices: List[StuckIlmIndex]) -> str:
    """Render stuck ILM indices as a fixed-width table."""
    if not indices:
        return "No stuck ILM indices found.\n"

    headers = ("Index", "Health", "Step", "Issue")
    rows = [
        (
            item.index_name,
            item.health,
            item.step or "-",
            item.issue,
        )
        for item in indices
    ]

    widths = [
        max(len(headers[idx]), *(len(row[idx]) for row in rows))
        for idx in range(len(headers))
    ]

    def _row(values: tuple[str, str, str, str]) -> str:
        return (
            f"{values[0]:<{widths[0]}}  "
            f"{values[1]:<{widths[1]}}  "
            f"{values[2]:<{widths[2]}}  "
            f"{values[3]}"
        )

    lines = [
        _row(headers),
        _row(tuple("-" * width for width in widths)),  # type: ignore[arg-type]
    ]
    lines.extend(_row(row) for row in rows)
    return "\n".join(lines) + "\n"

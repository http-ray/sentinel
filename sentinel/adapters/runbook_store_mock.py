"""Mock runbook store that loads markdown runbooks from ``runbooks/``.

Each runbook is a markdown file with a lightweight YAML-ish frontmatter block:

    ---
    id: checkout-5xx
    title: Checkout 5xx / payment failures
    services: [checkout-service]
    tags: [5xx, payments, retry]
    summary: Steps for elevated checkout error rates.
    ---
    <markdown body>
"""

from __future__ import annotations

from pathlib import Path

from sentinel.config import get_settings
from sentinel.models import Runbook


def _parse_runbook(path: Path) -> Runbook:
    text = path.read_text("utf-8")
    meta: dict[str, str] = {}
    body = text

    if text.lstrip().startswith("---"):
        stripped = text.lstrip()
        _, _, rest = stripped.partition("---")
        front, sep, body = rest.partition("---")
        if not sep:  # no closing fence; treat whole thing as body
            front, body = "", text
        for line in front.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            meta[key.strip().lower()] = value.strip()

    def _list(raw: str) -> list[str]:
        raw = raw.strip().strip("[]")
        return [item.strip() for item in raw.split(",") if item.strip()]

    return Runbook(
        id=meta.get("id", path.stem),
        title=meta.get("title", path.stem),
        services=_list(meta.get("services", "")),
        tags=_list(meta.get("tags", "")),
        summary=meta.get("summary", ""),
        body=body.strip(),
        path=str(path),
    )


class MockRunbookStore:
    def __init__(self, runbooks_dir: Path | None = None) -> None:
        self._dir = runbooks_dir or get_settings().runbooks_dir

    def all_runbooks(self) -> list[Runbook]:
        if not self._dir.exists():
            return []
        return [_parse_runbook(p) for p in sorted(self._dir.glob("*.md"))]

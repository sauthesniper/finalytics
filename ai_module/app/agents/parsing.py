"""Shared helpers for turning raw LLM text into (summary, bullets)."""
import re
from typing import Tuple, List

_BULLET_PREFIX = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s*")


def _is_bullet(line: str) -> bool:
    return bool(re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", line))


def _clean_bullet(line: str) -> str:
    """Strip any/all leading bullet markers (handles doubled '- - ')."""
    prev = None
    cur = line.strip()
    while cur != prev:
        prev = cur
        cur = _BULLET_PREFIX.sub("", cur).strip()
    return cur


def parse_summary_bullets(text: str) -> Tuple[str, List[str]]:
    """Split LLM output into a summary paragraph and a list of bullets."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    bullets = [_clean_bullet(l) for l in lines if _is_bullet(l)]
    bullets = [b for b in bullets if b]
    summary_lines = [l for l in lines if not _is_bullet(l)]
    summary = " ".join(summary_lines).strip() or (text or "").strip()
    return summary, bullets

import re

_ORDER_BY_RE = re.compile(r"\border\s+by\b", re.IGNORECASE)
_LIMIT_RE = re.compile(r"\blimit\b", re.IGNORECASE)
_OFFSET_RE = re.compile(r"\boffset\b", re.IGNORECASE)


def apply_limit_offset_keep_order(base_query: str, *, limit: int, offset: int) -> str:
    """
    MVP FULL pagination helper.

    Requirements:
    - base_query must contain ORDER BY (deterministic paging)
    - base_query must NOT contain LIMIT/OFFSET (runner applies them)
    """
    q = (base_query or "").strip().rstrip(";")

    if not _ORDER_BY_RE.search(q):
        raise ValueError("FULL mode requires deterministic ORDER BY in source_query.")

    if _LIMIT_RE.search(q) or _OFFSET_RE.search(q):
        raise ValueError(
            "source_query must not contain LIMIT/OFFSET; pagination is handled by runner."
        )

    return f"{q} LIMIT {limit} OFFSET {offset}"

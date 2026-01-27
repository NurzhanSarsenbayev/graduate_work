import re

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_sql_ident(name: str, *, what: str) -> str:
    n = (name or "").strip()
    if not _IDENT_RE.fullmatch(n):
        raise ValueError(
            f"Invalid {what}: {n!r}. " "Expected SQL identifier (column alias), e.g. 'updated_at'"
        )
    return n

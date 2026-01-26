def ctx_prefix(*, pid: str, pname: str, rid: str, attempt: int | None = None) -> str:
    base = f"pid={pid} name={pname} run={rid}"
    return f"{base} att={attempt}" if attempt is not None else base

import pytest

from src.runner.services.sql_pagination import apply_limit_offset_keep_order


def test_apply_limit_offset_appends_limit_offset():
    q = apply_limit_offset_keep_order(
        "SELECT * FROM t ORDER BY id",
        limit=10,
        offset=20,
    )
    assert q.endswith("LIMIT 10 OFFSET 20")
    assert "ORDER BY" in q.upper()


def test_apply_limit_offset_strips_semicolon():
    q = apply_limit_offset_keep_order(
        "SELECT * FROM t ORDER BY id;",
        limit=5,
        offset=0,
    )
    assert q.endswith("LIMIT 5 OFFSET 0")
    assert not q.strip().endswith(";")


def test_apply_limit_offset_requires_order_by():
    with pytest.raises(ValueError):
        apply_limit_offset_keep_order(
            "SELECT * FROM t",
            limit=10,
            offset=0,
        )


def test_apply_limit_offset_rejects_limit_offset_in_source_query():
    with pytest.raises(ValueError):
        apply_limit_offset_keep_order(
            "SELECT * FROM t ORDER BY id LIMIT 10",
            limit=10,
            offset=0,
        )

    with pytest.raises(ValueError):
        apply_limit_offset_keep_order(
            "SELECT * FROM t ORDER BY id OFFSET 5",
            limit=10,
            offset=0,
        )

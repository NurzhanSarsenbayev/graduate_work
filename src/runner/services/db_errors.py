from __future__ import annotations

import asyncpg
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError


def is_db_disconnect(exc: BaseException) -> bool:
    # SQLAlchemy wrappers
    if isinstance(exc, (OperationalError, InterfaceError)):
        return True
    if (isinstance(exc, DBAPIError) and
            getattr(exc, "connection_invalidated", False)):
        return True

    # asyncpg / OS-level
    if isinstance(exc, (asyncpg.PostgresError, OSError)):
        msg = str(exc).lower()
        return (
            "connection is closed" in msg
            or "connection was closed" in msg
            or "connection does not exist" in msg
            or "connection refused" in msg
            or "connect call failed" in msg
            or "no address associated with hostname" in msg
            or "the database system is starting up" in msg
            or "closed in the middle of operation" in msg
        )

    msg = str(exc).lower()
    return "no address associated with hostname" in msg

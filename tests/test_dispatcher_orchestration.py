import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.app.core.enums import PipelineStatus
from src.runner.orchestration.dispatcher import PipelineDispatcher


class DummyPipeline(SimpleNamespace):
    pass


@pytest.mark.asyncio
async def test_run_requested_success_finalizes_to_idle(monkeypatch):
    session = AsyncMock()
    executor = AsyncMock()
    pipelines = AsyncMock()

    claimed = DummyPipeline(
        id="pid-1",
        name="p1",
        status=PipelineStatus.RUN_REQUESTED.value,
        tasks=(),
        mode="full",
    )
    pipelines.claim_run_requested.return_value = claimed

    snap = DummyPipeline(
        id="pid-1", name="p1", tasks=(), mode="full", status=PipelineStatus.RUNNING.value
    )

    import src.runner.orchestration.dispatcher as disp_mod

    monkeypatch.setattr(disp_mod, "snapshot_pipeline_with_tasks", AsyncMock(return_value=snap))

    executor.execute.return_value = SimpleNamespace(rows_read=1, rows_written=1)

    pipelines.get_status.return_value = PipelineStatus.RUNNING.value
    pipelines.finish_running_to_idle.return_value = True

    d = PipelineDispatcher(
        executor=executor, pipelines=pipelines, max_attempts=3, backoff_seconds=(0, 0, 0)
    )
    await d.dispatch(session, claimed)

    executor.execute.assert_awaited_once()
    pipelines.finish_running_to_idle.assert_awaited_once_with(session, "pid-1")


@pytest.mark.asyncio
async def test_run_requested_if_paused_do_not_finalize(monkeypatch):
    session = AsyncMock()
    executor = AsyncMock()
    pipelines = AsyncMock()

    claimed = DummyPipeline(id="pid-1", name="p1", status=PipelineStatus.RUN_REQUESTED.value)
    pipelines.claim_run_requested.return_value = claimed

    snap = DummyPipeline(id="pid-1", name="p1", tasks=(), mode="full")
    import src.runner.orchestration.dispatcher as disp_mod

    monkeypatch.setattr(disp_mod, "snapshot_pipeline_with_tasks", AsyncMock(return_value=snap))

    executor.execute.return_value = SimpleNamespace(rows_read=1, rows_written=1)

    pipelines.get_status.return_value = PipelineStatus.PAUSED.value

    d = PipelineDispatcher(
        executor=executor, pipelines=pipelines, max_attempts=3, backoff_seconds=(0, 0, 0)
    )
    await d.dispatch(session, claimed)

    pipelines.finish_running_to_idle.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_on_non_disconnect_error(monkeypatch):
    session = AsyncMock()
    executor = AsyncMock()
    pipelines = AsyncMock()

    claimed = DummyPipeline(id="pid-1", name="p1", status=PipelineStatus.RUN_REQUESTED.value)
    pipelines.claim_run_requested.return_value = claimed

    snap = DummyPipeline(id="pid-1", name="p1", tasks=(), mode="full")
    import src.runner.orchestration.dispatcher as disp_mod

    monkeypatch.setattr(disp_mod, "snapshot_pipeline_with_tasks", AsyncMock(return_value=snap))

    monkeypatch.setattr(disp_mod, "is_db_disconnect", lambda exc: False)

    class Boom(Exception):
        pass

    executor.execute.side_effect = [
        Boom("1"),
        Boom("2"),
        SimpleNamespace(rows_read=1, rows_written=1),
    ]

    pipelines.get_status.return_value = PipelineStatus.RUNNING.value
    pipelines.finish_running_to_idle.return_value = True

    async def fake_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    d = PipelineDispatcher(
        executor=executor, pipelines=pipelines, max_attempts=3, backoff_seconds=(0.01, 0.02, 0.04)
    )
    await d.dispatch(session, claimed)

    assert executor.execute.await_count == 3
    pipelines.fail_if_active.assert_not_awaited()


@pytest.mark.asyncio
async def test_db_disconnect_exits_without_failing_pipeline(monkeypatch):
    session = AsyncMock()
    executor = AsyncMock()
    pipelines = AsyncMock()

    claimed = DummyPipeline(id="pid-1", name="p1", status=PipelineStatus.RUN_REQUESTED.value)
    pipelines.claim_run_requested.return_value = claimed

    snap = DummyPipeline(id="pid-1", name="p1", tasks=(), mode="full")
    import src.runner.orchestration.dispatcher as disp_mod

    monkeypatch.setattr(disp_mod, "snapshot_pipeline_with_tasks", AsyncMock(return_value=snap))

    class DbDown(Exception):
        pass

    executor.execute.side_effect = DbDown("down")
    monkeypatch.setattr(disp_mod, "is_db_disconnect", lambda exc: True)

    d = PipelineDispatcher(executor=executor, pipelines=pipelines)
    await d.dispatch(session, claimed)

    pipelines.fail_if_active.assert_not_awaited()


@pytest.mark.asyncio
async def test_pause_requested_applies_pause():
    session = AsyncMock()
    executor = AsyncMock()
    pipelines = AsyncMock()

    pipe = DummyPipeline(id="pid-1", name="p1", status=PipelineStatus.PAUSE_REQUESTED.value)

    d = PipelineDispatcher(executor=executor, pipelines=pipelines)
    await d.dispatch(session, pipe)

    pipelines.apply_pause_requested.assert_awaited_once_with(session, "pid-1")
    executor.execute.assert_not_awaited()

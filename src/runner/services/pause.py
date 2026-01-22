import logging
from src.app.core import PipelineStatus
from src.runner.orchestration.context import ExecutionContext

logger = logging.getLogger("etl_runner")

async def _pause_if_requested(
    ctx: ExecutionContext,
    pipeline_id: str,
) -> bool:
    status = await ctx.pipelines.get_status(ctx.session, pipeline_id)
    if status == PipelineStatus.PAUSE_REQUESTED.value:
        await ctx.pipelines.apply_pause_requested(
            ctx.session, pipeline_id)  # commit inside
        logger.info("Pause requested:"
                    " pipeline id=%s -> PAUSED (after batch)", pipeline_id)
        return True
    return False
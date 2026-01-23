import pytest
from pydantic import ValidationError

from src.app.schemas.pipelines import PipelineCreate


def test_incremental_requires_inc_key_and_id_key():
    with pytest.raises(ValidationError) as e:
        PipelineCreate(
            name="inc",
            enabled=True,
            type="SQL",
            mode="incremental",
            source_query="select 1",
            target_table="analytics.film_dim",
            incremental_key=None,
            incremental_id_key=None,
        )
    msg = str(e.value)
    assert "incremental_key" in msg
    assert "incremental_id_key" in msg


def test_python_pipeline_requires_python_module():
    with pytest.raises(ValidationError) as e:
        PipelineCreate(
            name="py_task",
            enabled=True,
            type="PYTHON",
            mode="full",
            source_query="select 1",
            target_table="analytics.film_dim",
            python_module=None,
        )

    msg = str(e.value)
    assert "python_module" in msg


def test_python_module_must_be_in_allowlisted_namespace():
    with pytest.raises(ValidationError) as e:
        PipelineCreate(
            name="py_task",
            enabled=True,
            type="PYTHON",
            mode="full",
            source_query="select 1",
            target_table="analytics.film_dim",
            python_module="evil.module",
        )

    msg = str(e.value)
    assert "python_module" in msg


@pytest.mark.parametrize("bad_name", ["", "   ", "x" * 101, "bad space", "bad/slash"])
def test_pipeline_name_validation(bad_name):
    with pytest.raises(ValidationError):
        PipelineCreate(
            name=bad_name,
            enabled=True,
            type="SQL",
            mode="full",
            source_query="select 1",
            target_table="analytics.film_dim",
        )


@pytest.mark.parametrize("size", [0, -1, 100_001])
def test_batch_size_bounds(size):
    with pytest.raises(ValidationError):
        PipelineCreate(
            name="ok",
            enabled=True,
            type="SQL",
            mode="full",
            source_query="select 1",
            target_table="analytics.film_dim",
            batch_size=size,
        )

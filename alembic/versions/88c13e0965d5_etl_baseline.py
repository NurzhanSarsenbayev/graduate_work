from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "88c13e0965d5"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) schema + extension (для gen_random_uuid())
    op.execute("CREATE SCHEMA IF NOT EXISTS etl;")
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    # 2) etl_pipelines
    op.create_table(
        "etl_pipelines",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("source_query", sa.Text(), nullable=True),
        sa.Column("python_module", sa.Text(), nullable=True),
        sa.Column("target_table", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("incremental_key", sa.Text(), nullable=True),
        sa.Column("incremental_id_key", sa.Text(), nullable=True),  # <-- сразу добавили
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default=sa.text("1000")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'IDLE'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("type IN ('SQL', 'PYTHON', 'ES')", name="etl_pipelines_type_check"),
        sa.CheckConstraint("mode IN ('full', 'incremental')", name="etl_pipelines_mode_check"),
        sa.CheckConstraint(
            "status IN ('IDLE', 'RUN_REQUESTED', 'RUNNING', 'PAUSE_REQUESTED', 'PAUSED', 'FAILED')",
            name="etl_pipelines_status_check",
        ),
        schema="etl",
    )

    # 3) etl_pipeline_tasks
    op.create_table(
        "etl_pipeline_tasks",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "pipeline_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("etl.etl_pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=True),
        sa.Column("target_table", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("pipeline_id", "order_index", name="etl_pipeline_tasks_order_uq"),
        sa.CheckConstraint("task_type IN ('SQL', 'PYTHON')", name="etl_pipeline_tasks_type_check"),
        schema="etl",
    )

    # 4) etl_state
    op.create_table(
        "etl_state",
        sa.Column(
            "pipeline_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("etl.etl_pipelines.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("last_processed_id", sa.Text(), nullable=True),
        sa.Column("last_processed_value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="etl",
    )

    # 5) etl_runs
    op.create_table(
        "etl_runs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "pipeline_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("etl.etl_pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # Совет: лучше NOT NULL DEFAULT 0, чтобы repo/логика не ловили None
        sa.Column("rows_read", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rows_written", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'RUNNING'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('RUNNING', 'SUCCESS', 'FAILED')", name="etl_runs_status_check"),
        schema="etl",
    )

    op.create_index(
        "ix_etl_runs_pipeline_id_started_at",
        "etl_runs",
        ["pipeline_id", "started_at"],
        unique=False,
        schema="etl",
        postgresql_using="btree",
        postgresql_ops={"started_at": "DESC"},
    )
    # ⚠️ Если выше строка с postgresql_ops упрётся — проще так:
    # op.execute("CREATE INDEX IF NOT EXISTS ix_etl_runs_pipeline_id_started_at ON etl.etl_runs (pipeline_id, started_at DESC);")


def downgrade() -> None:
    # удаляем в обратном порядке зависимостей
    op.drop_index("ix_etl_runs_pipeline_id_started_at", table_name="etl_runs", schema="etl")
    op.drop_table("etl_runs", schema="etl")
    op.drop_table("etl_state", schema="etl")
    op.drop_table("etl_pipeline_tasks", schema="etl")
    op.drop_table("etl_pipelines", schema="etl")
    # schema и extension обычно не трогаем (чтобы не снести чужое), но если хочешь:
    # op.execute("DROP SCHEMA IF EXISTS etl CASCADE;")
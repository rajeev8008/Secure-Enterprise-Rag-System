"""Add document ingestion fields."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column(
        "documents",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute("UPDATE documents SET status = 'PENDING' WHERE status = 'pending'")


def downgrade() -> None:
    op.drop_column("documents", "updated_at")
    op.drop_column("documents", "chunk_count")

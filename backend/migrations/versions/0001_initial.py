"""initial schema: users + collection_entries

Revision ID: 0001
Revises:
Create Date: 2026-09-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("google_sub", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("picture_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "collection_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pokemon_id", sa.Integer(), nullable=False),
        sa.Column("pokemon_name", sa.String(length=255), nullable=False),
        sa.Column("sprite_url", sa.String(length=1024), nullable=True),
        sa.Column("types", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("nickname", sa.String(length=255), nullable=True),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("custom_image_url", sa.String(length=1024), nullable=True),
        sa.Column("caught_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_collection_entries_user_id", "collection_entries", ["user_id"]
    )
    op.create_index(
        "ix_collection_entries_pokemon_id", "collection_entries", ["pokemon_id"]
    )


def downgrade() -> None:
    op.drop_table("collection_entries")
    op.drop_table("users")

"""widen mime_type column from VARCHAR(64) to VARCHAR(255)

Revision ID: 002_widen_mime_type
Revises: c0e7f74e2e99
Create Date: 2026-11-07

Fixes: DOCX MIME type 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
       is 71 chars which overflowed the old VARCHAR(64) limit → 500 on upload.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_widen_mime_type'
down_revision: Union[str, None] = 'c0e7f74e2e99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'documents',
        'mime_type',
        existing_type=sa.String(length=64),
        type_=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'documents',
        'mime_type',
        existing_type=sa.String(length=255),
        type_=sa.String(length=64),
        existing_nullable=False,
    )

"""Add optional connection metadata (protocol, source port, destination port) to network_history.

The three columns are nullable, so every existing row simply has no value and nothing is rewritten. A new
database created from database/schema.sql already has them; the migration checks for that and does nothing.

Apply to an existing database (online mode only):  alembic upgrade head

Revision ID: 0001_connection_metadata
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_connection_metadata"
down_revision = None
branch_labels = None
depends_on = None

# In this order, right after observed_at, exactly as in database/schema.sql.
_COLUMNS = (
    ("protocol", "ENUM('TCP', 'UDP') NULL"),
    ("source_port", "SMALLINT UNSIGNED NULL"),
    ("destination_port", "SMALLINT UNSIGNED NULL"),
)


def _existing_columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("network_history")}


def upgrade() -> None:
    present = _existing_columns()
    after = "observed_at"
    for name, definition in _COLUMNS:
        if name not in present:
            op.execute(f"ALTER TABLE network_history ADD COLUMN {name} {definition} AFTER {after}")
        after = name


def downgrade() -> None:
    """Drops the three columns and the values in them (the events themselves are kept)."""
    present = _existing_columns()
    for name, _ in reversed(_COLUMNS):
        if name in present:
            op.drop_column("network_history", name)

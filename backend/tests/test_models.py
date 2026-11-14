"""Guards on the schema itself. No database needed — these read the metadata.

The rules checked here are the ones from docs/architecture.md that are easy to
break by accident when adding a table six weeks from now.
"""

import pytest
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.db.base import Base

# The only tables that are not inside a workspace: a workspace cannot contain
# itself, a user exists before they belong to anything, and a user's
# notification settings belong to the person, applying in every workspace they
# are in (GitHub #82). Keyed by user_id, which cascades with the user.
GLOBAL_TABLES = {"workspaces", "users", "notification_settings"}

TENANT_TABLES = sorted(set(Base.metadata.tables) - GLOBAL_TABLES)


def test_mappers_configure() -> None:
    """Every relationship resolves. Catches typos in back_populates at import."""
    configure_mappers()


def test_every_table_is_accounted_for() -> None:
    """A new table is either global or tenant-scoped — no third option."""
    assert set(Base.metadata.tables) == GLOBAL_TABLES | set(TENANT_TABLES)


@pytest.mark.parametrize("table_name", TENANT_TABLES)
def test_tenant_table_has_non_nullable_workspace_id(table_name: str) -> None:
    """The rule that keeps one tenant's data out of another's queries.

    A nullable workspace_id is worse than none at all: the column looks like a
    filter but lets rows through that belong to nobody.
    """
    table = Base.metadata.tables[table_name]
    assert "workspace_id" in table.columns, (
        f"{table_name} is tenant-scoped but has no workspace_id — "
        "see docs/architecture.md"
    )
    assert not table.columns["workspace_id"].nullable


@pytest.mark.parametrize("table_name", TENANT_TABLES)
def test_tenant_table_is_indexed_on_workspace_id_first(table_name: str) -> None:
    """Every query narrows to one workspace first, so an index must too."""
    table = Base.metadata.tables[table_name]
    leading = {
        tuple(index.columns.keys())[0]
        for index in table.indexes
        if len(index.columns) > 0
    }
    assert "workspace_id" in leading, (
        f"{table_name} has no index leading with workspace_id"
    )


def test_warranty_status_is_not_stored() -> None:
    """Status is computed from end_date and today — see docs/architecture.md.

    A stored copy is wrong the moment the clock passes it, and nothing would
    tell us.
    """
    assert "status" not in Base.metadata.tables["warranties"].columns

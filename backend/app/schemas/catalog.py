"""Response shapes for the four catalog lists.

These are the pickers on the Add Asset form and the filters on the Assets List
— `/categories`, `/vendors`, `/departments`, `/locations`. The four tables are
identical in shape (see app/models/catalog.py), so one pair of schemas serves
all four rather than four near-identical copies.

`{id, name}` matches how a catalog row already appears nested inside the asset
detail payload in docs/api.md ("category": {"id": ..., "name": ...}), so the
frontend sees the same object whichever endpoint it came from.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

#: A catalog name: trimmed first, then required to be non-empty and to fit the
#: column. Order matters — validating length before stripping would let "   "
#: through `min_length=1` and store a row with a blank name.
CatalogName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


class CatalogItem(BaseModel):
    """One option in a picker: a category, vendor, department or location."""

    # Lets Pydantic read straight off the SQLAlchemy object (c.id, c.name)
    # instead of us building a dict by hand.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class CatalogCreate(BaseModel):
    """Adding one option to a list — a category, vendor, department or location.

    Only a name: these tables hold nothing else (app/models/catalog.py). The
    length matches the column, so an over-long name is a 422 naming the field
    rather than a database error.
    """

    name: CatalogName


class CatalogUpdate(BaseModel):
    """Renaming one option. The name is all these tables hold, so it is all
    there is to change — which makes PUT-shaped semantics and PATCH-shaped
    semantics identical here, and `name` required rather than optional.
    """

    name: CatalogName


class CatalogList(BaseModel):
    """Envelope for the four GET endpoints.

    Deliberately not paginated. These lists fill a dropdown, so the caller
    wants all of them at once — a page of 20 categories would just make the
    frontend loop to rebuild the whole list. They are bounded by how many a
    workspace chooses to create. If one ever grows past a few hundred, add
    paging then and match the `{items, total, page, page_size}` shape that
    `GET /assets` uses.
    """

    items: list[CatalogItem]

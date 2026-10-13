from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Parent class for every SQLAlchemy model.

    Alembic discovers tables through this class, so every model must inherit
    from it and be imported in app/models/__init__.py.
    """

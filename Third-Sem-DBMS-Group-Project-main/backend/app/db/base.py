from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base. The schema comes from database/schema.sql; never create or drop tables from the models."""

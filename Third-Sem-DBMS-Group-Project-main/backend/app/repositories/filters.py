from sqlalchemy.sql.elements import ColumnElement


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def contains(column, term: str) -> ColumnElement[bool]:
    return column.like(f"%{escape_like(term)}%", escape="\\")

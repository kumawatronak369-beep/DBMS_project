from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

engine = create_engine(
    get_settings().sqlalchemy_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    hide_parameters=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

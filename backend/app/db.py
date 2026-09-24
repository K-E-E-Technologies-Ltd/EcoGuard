from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import get_settings

class Base(DeclarativeBase):
    pass

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True,
    connect_args={'check_same_thread': False, 'timeout': 30} if settings.database_url.startswith('sqlite') else {})
if settings.database_url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def _sqlite_fk(dbapi_conn, _):
        dbapi_conn.execute('PRAGMA foreign_keys=ON')
SessionLocal = sessionmaker(engine, expire_on_commit=False)

def get_db():
    with SessionLocal() as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise

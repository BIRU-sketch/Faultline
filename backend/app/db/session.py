from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool

Base = declarative_base()

_engine = None
_SessionFactory = sessionmaker(autocommit=False, autoflush=False)
SessionScoped = scoped_session(_SessionFactory)


def init_db(database_url: str):
    """Initialize database engine and scoped session."""
    global _engine, _SessionFactory

    engine_kwargs = {"echo": False}
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in database_url:
            engine_kwargs["poolclass"] = StaticPool

    _engine = create_engine(database_url, **engine_kwargs)

    # Enable foreign keys for SQLite
    if database_url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    _SessionFactory.configure(bind=_engine)

    # Import models here so Base knows about them before create_all
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=_engine)
    run_columns = {column["name"] for column in inspect(_engine).get_columns("runs")}
    with _engine.begin() as connection:
        for column_name in ("orchestration_metadata", "final_report"):
            if column_name not in run_columns:
                connection.execute(text(f"ALTER TABLE runs ADD COLUMN {column_name} JSON"))
    return _engine


def get_session():
    """Returns the current scoped session."""
    return SessionScoped()


def close_session(exception=None):
    """Teardown handler to remove the scoped session after request."""
    SessionScoped.remove()

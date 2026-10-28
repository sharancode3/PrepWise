from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker


class Database:
    def __init__(self, url: str):
        if not url.startswith("sqlite:"):
            raise ValueError("Foundation supports SQLite; hosted databases require a reviewed configuration")
        self.engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 5})

        @event.listens_for(self.engine, "connect")
        def configure_connection(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def ready(self) -> bool:
        try:
            with self.engine.connect() as connection:
                if not inspect(connection).has_table("alembic_version"):
                    return False
                return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none() in ("0001_foundation", "0002_projects_and_scopes")
        except Exception:
            return False

    def enable_wal(self) -> None:
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.exec_driver_sql("PRAGMA journal_mode=WAL")

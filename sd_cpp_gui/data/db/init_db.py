"""
Database initialization and migration logic.
"""

from threading import Lock
from typing import Any, List, Optional

import peewee
from playhouse.migrate import SqliteMigrator, migrate

from sd_cpp_gui.data.db.database import db as db_instance
from sd_cpp_gui.data.db.models import (
    EmbeddingEntry,
    HistoryEntry,
    LoraEntry,
    ModelEntry,
    QueueEntry,
    SettingModel,
)
from sd_cpp_gui.data.db.models import db as db_proxy


class Database:
    """Singleton for Database initialization."""

    _instance: Optional["Database"] = None
    _lock: Lock = Lock()

    def __new__(cls) -> "Database":
        """Logic: Singleton instantiation calling _init_db."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Database, cls).__new__(cls)
                cls._instance._init_db()  # pylint: disable=protected-access
        return cls._instance

    def _init_db(self) -> None:
        """Initializes database connection and structure.

        Logic: Connects DB, creates tables, and runs migrations."""
        db_proxy.initialize(db_instance)
        db_instance.connect(reuse_if_open=True)
        db_instance.create_tables(
            [
                SettingModel,
                ModelEntry,
                LoraEntry,
                EmbeddingEntry,
                HistoryEntry,
                QueueEntry,
            ],
            safe=True,
        )
        self._check_schema_updates()

    def _check_schema_updates(self) -> None:
        """Checks and applies schema migrations.

        Logic: Checks columns and applies migrations if needed."""
        migrator = SqliteMigrator(db_instance)
        hist_cols = [c.name for c in db_instance.get_columns("history")]
        if "metadata" not in hist_cols:
            self._safe_migrate(
                migrator.add_column(
                    "history", "metadata", peewee.TextField(null=True)
                )
            )
        lora_cols = [c.name for c in db_instance.get_columns("loras")]
        self._apply_network_migrations(migrator, "loras", lora_cols)
        emb_cols = [c.name for c in db_instance.get_columns("embeddings")]
        self._apply_network_migrations(migrator, "embeddings", emb_cols)
        model_cols = [c.name for c in db_instance.get_columns("models")]
        self._apply_remote_fields(migrator, "models", model_cols)

    def _safe_migrate(self, operation: Any) -> None:
        """Executes a migration operation safely.

        Logic: Executes migration ignoring errors if column exists."""
        try:
            migrate(operation)
        except peewee.OperationalError:
            pass

    def _apply_network_migrations(
        self, migrator: SqliteMigrator, table_name: str, columns: List[str]
    ) -> None:
        """Applies migrations for LoRA and Embedding tables.

        Logic: Adds missing columns to network tables."""
        if "dir_path" not in columns:
            self._safe_migrate(
                migrator.add_column(
                    table_name, "dir_path", peewee.TextField(default="")
                )
            )
        if "filename" not in columns:
            self._safe_migrate(
                migrator.add_column(
                    table_name, "filename", peewee.TextField(default="")
                )
            )
        if "alias" not in columns:
            self._safe_migrate(
                migrator.add_column(
                    table_name, "alias", peewee.TextField(null=True)
                )
            )
        if "trigger_words" not in columns:
            self._safe_migrate(
                migrator.add_column(
                    table_name, "trigger_words", peewee.TextField(default="")
                )
            )
        if "preferred_strength" not in columns:
            self._safe_migrate(
                migrator.add_column(
                    table_name,
                    "preferred_strength",
                    peewee.FloatField(default=1.0),
                )
            )
        current_cols = [c.name for c in db_instance.get_columns(table_name)]
        self._apply_remote_fields(migrator, table_name, current_cols)

    def _apply_remote_fields(
        self, migrator: SqliteMigrator, table_name: str, columns: List[str]
    ) -> None:
        """Adds remote source tracking columns if missing.

        Logic: Adds remote source columns to tables."""
        if "remote_source" not in columns:
            self._safe_migrate(
                migrator.add_column(
                    table_name, "remote_source", peewee.TextField(null=True)
                )
            )
        if "remote_id" not in columns:
            self._safe_migrate(
                migrator.add_column(
                    table_name, "remote_id", peewee.TextField(null=True)
                )
            )
        if "remote_version_id" not in columns:
            self._safe_migrate(
                migrator.add_column(
                    table_name, "remote_version_id", peewee.TextField(null=True)
                )
            )
        if "base_model" not in columns:
            self._safe_migrate(
                migrator.add_column(
                    table_name, "base_model", peewee.TextField(null=True)
                )
            )
        if "description" not in columns:
            self._safe_migrate(
                migrator.add_column(
                    table_name, "description", peewee.TextField(null=True)
                )
            )
        if "content_hash" not in columns:
            self._safe_migrate(
                migrator.add_column(
                    table_name, "content_hash", peewee.TextField(null=True)
                )
            )
            try:
                db_instance.execute_sql(
                    "CREATE INDEX IF NOT EXISTS "
                    f"{table_name}_content_hash ON {table_name}(content_hash)"
                )
            except Exception:
                pass

    def get_connection(self) -> peewee.Database:
        """Returns the active connection.

        Logic: Returns DB instance."""
        return db_instance

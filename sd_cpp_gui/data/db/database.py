"""
Database connection configuration.
"""

import os
import time

import peewee
from playhouse.sqlite_ext import SqliteDatabase

from sd_cpp_gui.infrastructure.paths import DATA_DIR

DB_FILE: str = os.path.join(DATA_DIR, "app_data.sqlite")


class RetryDatabase(SqliteDatabase):
    """
    Wrapper that automatically retries queries if the DB is locked.
    commit is deprecated, only for compatibility
    """

    def execute_sql(self, sql, params=None, _commit=None):
        """Logic: Retries SQL execution on lock error."""
        for i in range(5):
            try:
                return super().execute_sql(sql, params)
            except peewee.OperationalError as e:
                if "locked" in str(e).lower() and i < 4:
                    time.sleep(0.1 * (i + 1))
                else:
                    raise e


db = RetryDatabase(
    DB_FILE,
    check_same_thread=False,
    timeout=30,
    pragmas={
        "cache_size": -1024 * 64,
        "journal_mode": "wal",
        "synchronous": "NORMAL",
    },
)

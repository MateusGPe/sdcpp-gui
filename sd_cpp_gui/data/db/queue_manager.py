"""
Queue Manager
"""

import json
import uuid
from datetime import datetime
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

import peewee

from sd_cpp_gui.data.db.database import db
from sd_cpp_gui.data.db.init_db import Database
from sd_cpp_gui.data.db.models import QueueData, QueueEntry
from sd_cpp_gui.infrastructure.logger import get_logger

logger = get_logger(__name__)


class QueueManager:
    """Manages the generation queue."""

    _sanitized = False

    def __init__(self) -> None:
        """
        Logic: Initializes queue manager, sanitizes pending items on startup.
        """
        Database()
        self._lock = Lock()
        self._subscribers: List[Callable[[], None]] = []
        if not QueueManager._sanitized:
            self._sanitize_on_startup()
            QueueManager._sanitized = True

    def _sanitize_on_startup(self) -> None:
        """Reset items stuck in 'running' state from previous crash.

        Logic: Resets 'running' items to 'pending'."""
        with self._lock:
            QueueEntry.update(status="pending").where(
                QueueEntry.status == "running"
            ).execute()

    def subscribe(self, callback: Callable[[], None]) -> None:
        """Adds a callback to be notified of queue changes.

        Logic: Adds subscriber."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[], None]) -> None:
        """Removes a callback.

        Logic: Removes subscriber."""
        try:
            self._subscribers.remove(callback)
        except ValueError:
            pass

    def _notify_subscribers(self) -> None:
        """Notifies all subscribers of a change.

        Logic: Notifies all subscribers."""
        for callback in self._subscribers:
            try:
                callback()
            except Exception as e:
                logger.error(
                    "Error in queue subscriber callback: %s", e, exc_info=True
                )

    def add(
        self,
        model_id: str,
        prompt: str,
        compiled_params: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> QueueData:
        """
        Adds a new generation task to the queue.

        Args:
                model_id: ID of the model to use.
                prompt: The generation prompt.
                compiled_params: List of CLI parameters.
                metadata: Additional metadata for the task.

        Returns:
                The created QueueData dictionary.
        """
        with self._lock:
            uuid_str = str(uuid.uuid4())
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            params_json = json.dumps(compiled_params)
            metadata_json = json.dumps(metadata) if metadata else "{}"
            max_priority = QueueEntry.select(
                peewee.fn.MAX(QueueEntry.priority)
            ).scalar()
            if max_priority is None:
                max_priority = 0
            entry = QueueEntry.create(
                uuid=uuid_str,
                model_id=model_id,
                timestamp=timestamp_str,
                prompt=prompt,
                compiled_params=params_json,
                metadata=metadata_json,
                status="pending",
                priority=max_priority + 1,
            )
            self._notify_subscribers()
            return self._entry_to_dict(entry)

    def get_all(self) -> List[QueueData]:
        """Returns the entire queue, ordered by priority.

        Logic: Returns all queue items."""
        with self._lock:
            query = QueueEntry.select().order_by(QueueEntry.priority.asc())
            return [self._entry_to_dict(entry) for entry in query]

    def get_next(self) -> Optional[QueueData]:
        """
        Retrieves the next 'pending' item from the queue based on priority.

        Returns:
                The QueueData dictionary or None if the queue is empty.
        """
        with self._lock:
            entry = (
                QueueEntry.select()
                .where(QueueEntry.status == "pending")
                .order_by(QueueEntry.priority.asc())
                .first()
            )
            return self._entry_to_dict(entry) if entry else None

    def get(self, entry_uuid: str) -> Optional[QueueData]:
        """Gets a specific queue item by its UUID.

        Logic: Gets specific item by UUID."""
        with self._lock:
            entry = QueueEntry.get_or_none(QueueEntry.uuid == entry_uuid)
            return self._entry_to_dict(entry) if entry else None

    def update_status(self, entry_uuid: str, status: str) -> None:
        """
        Updates the status of a specific queue item.

        Args:
            entry_uuid: The UUID of the item.
            status: The new status (e.g., 'pending', 'running',
            'done', 'failed').
        """
        with self._lock:
            (
                QueueEntry.update(status=status)
                .where(QueueEntry.uuid == entry_uuid)
                .execute()
            )
            self._notify_subscribers()

    def remove(self, entry_uuid: str) -> None:
        """Removes an item from the queue.

        Logic: Deletes item."""
        with self._lock:
            QueueEntry.delete().where(QueueEntry.uuid == entry_uuid).execute()
            self._notify_subscribers()

    def clear(self) -> None:
        """Removes all items from the queue.

        Logic: Clears entire queue."""
        with self._lock:
            QueueEntry.delete().execute()
            self._notify_subscribers()

    def reorder(self, entry_uuid: str, new_priority: int) -> None:
        """
        Changes the priority of an item and shifts others to accommodate.

        Args:
                entry_uuid: The UUID of the item to move.
                new_priority: The target priority index.
        """
        with self._lock:
            with db.atomic():
                target_entry = QueueEntry.get_or_none(
                    QueueEntry.uuid == entry_uuid
                )
                if not target_entry:
                    return
                old_priority = target_entry.priority
                if old_priority == new_priority:
                    return
                if old_priority < new_priority:
                    QueueEntry.update(priority=QueueEntry.priority - 1).where(
                        (QueueEntry.priority > old_priority)
                        & (QueueEntry.priority <= new_priority)
                    ).execute()
                else:
                    QueueEntry.update(priority=QueueEntry.priority + 1).where(
                        (QueueEntry.priority >= new_priority)
                        & (QueueEntry.priority < old_priority)
                    ).execute()
                QueueEntry.update(priority=new_priority).where(
                    QueueEntry.uuid == entry_uuid
                ).execute()
                self._notify_subscribers()

    def sort_by_model(self) -> None:
        """Sorts pending items by model_id to minimize model switching.

        Logic: Reorders queue to group by model ID."""
        with self._lock, db.atomic():
            pending = QueueEntry.select().order_by(
                QueueEntry.status, QueueEntry.model_id, QueueEntry.priority
            )
            current_prio = 1
            for entry in pending:
                entry.priority = current_prio
                entry.save()
                current_prio += 1
            self._notify_subscribers()

    def _entry_to_dict(self, entry: QueueEntry) -> QueueData:
        """Logic: Converts DB entry to TypedDict."""
        try:
            c_params = (
                json.loads(str(entry.compiled_params))
                if entry.compiled_params
                else []
            )
        except (json.JSONDecodeError, TypeError):
            c_params = []
        try:
            meta = json.loads(str(entry.metadata)) if entry.metadata else {}
        except (json.JSONDecodeError, TypeError):
            meta = {}
        return QueueData(
            uuid=str(entry.uuid),
            model_id=str(entry.model_id),
            timestamp=str(entry.timestamp),
            prompt=str(entry.prompt),
            compiled_params=c_params,
            metadata=meta,
            status=str(entry.status),
            priority=entry.priority,  # type: ignore
        )

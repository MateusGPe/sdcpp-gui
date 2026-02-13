import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from peewee import SqliteDatabase

from sd_cpp_gui.infrastructure.logger import get_logger

logger = get_logger(__name__)

# Try importing RapidFuzz
try:
    from rapidfuzz import fuzz, process

    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


class AutocompleteService:
    def __init__(self, assets_path: Path):
        """Initializes service with DB path and internal structures."""
        self.db_path = assets_path

        # OPTIMIZATION: Only keep names in RAM for sorting/fuzzy.
        # Dropped _tags_meta (dict) and _bigrams_db (dict) to save memory.
        self._tags_names: List[str] = []

        self._active_triggers_map: Dict[str, List[str]] = {}
        self._active_triggers_list: List[str] = []

        self._loaded = False
        self._lock = threading.Lock()

        # Persistent DB connection for fast lookups
        self._db = None

        self.COLORS = {
            0: "#8be9fd",
            1: "#ff5555",
            3: "#bd93f9",
            4: "#50fa7b",
            5: "#ffb86c",
            99: "#f1fa8c",
        }

    def load(self):
        """Loads tag names into RAM for fast lookup."""
        if not self.db_path.exists():
            logger.error(
                f"Database not found at {self.db_path}. Run build_db.py first."
            )
            return

        with self._lock:
            t0 = time.time()

            # Initialize persistent connection
            if self._db is None:
                self._db = SqliteDatabase(
                    f"file:{self.db_path}?mode=ro", uri=True
                )

            try:
                self._db.connect(reuse_if_open=True)

                # OPTIMIZATION: Only fetch names.
                # We rely on the DB ORDER BY to ensure the list is
                # sorted by popularity.
                cursor = self._db.execute_sql(
                    "SELECT name FROM tag ORDER BY count DESC"
                )

                # Fetching one column is faster and uses less memory
                # than fetching all
                self._tags_names = [r[0] for r in cursor.fetchall()]

                self._loaded = True

                logger.info(
                    "Autocomplete service ready in %.3fs (Lightweight Mode)",
                    time.time() - t0,
                )

            except Exception as e:
                logger.error(f"Failed to load autocomplete database: {e}")
                self._loaded = False
                if not self._db.is_closed():
                    self._db.close()

    def on_state_change(
        self, event_type: str, key: str, value: Any = None
    ) -> None:
        """
        Updates active triggers based on network changes.
        Listens: StateManager events (lora, embedding).
        """
        if event_type == "reset":
            keep = False
            if isinstance(value, dict):
                keep = value.get("keep_networks", False)
            if not keep:
                self._active_triggers_map.clear()
                self._update_active_triggers_list()
            return

        if event_type not in ("lora", "embedding"):
            return

        unique_key = f"{event_type}:{key}"

        if value is None:
            if unique_key in self._active_triggers_map:
                del self._active_triggers_map[unique_key]
                self._update_active_triggers_list()
        else:
            triggers = getattr(value, "triggers", None)
            if triggers:
                t_list = [
                    t.strip().lower() for t in triggers.split(",") if t.strip()
                ]
                if t_list:
                    self._active_triggers_map[unique_key] = t_list
                    self._update_active_triggers_list()
                elif unique_key in self._active_triggers_map:
                    del self._active_triggers_map[unique_key]
                    self._update_active_triggers_list()
            elif unique_key in self._active_triggers_map:
                del self._active_triggers_map[unique_key]
                self._update_active_triggers_list()

    def _update_active_triggers_list(self):
        """Rebuilds sorted list of active triggers from map."""
        all_triggers = set().union(*self._active_triggers_map.values())
        logger.debug("Active triggers updated: %s", all_triggers)
        self._active_triggers_list = sorted(list(all_triggers))

    def search(
        self, query: str, limit: int = 20
    ) -> List[Tuple[str, str, str, int, str]]:
        """
        Performs multi-stage autocomplete search (Context -> Prefix -> Fuzzy).
        Returns: List[(display, value, color, category, name)].
        """
        if not self._loaded or not query:
            return []

        # 1. Parsing
        query = query.lower().lstrip()
        parts = re.split(r"[\s<>\(\)\{\}\[\],\.\|:]", query)
        last_empty = False

        if parts[-1] == "":
            last_empty = True
        parts = list(filter(None, parts))
        if last_empty:
            parts.append("")

        target_fragment = parts[-1]
        context_word = parts[-2] if len(parts) > 1 else None

        if context_word:
            context_word = context_word.strip(",.")

        prefix_str = " ".join(parts[:-1])

        results = []
        seen = set()

        # 2. Context Search (Optimized: Direct SQL)
        if context_word:
            self._search_bigrams(
                context_word, target_fragment, prefix_str, results, seen, limit
            )

        # 2.5 Active Triggers Search
        if (
            len(results) < limit
            and self._active_triggers_list
            and len(target_fragment) >= 1
        ):
            for trigger in self._active_triggers_list:
                if trigger.lower().startswith(target_fragment):
                    if trigger in seen:
                        continue
                    full_value = (
                        f"{prefix_str} {trigger}" if prefix_str else trigger
                    )
                    display = f"{trigger} (Active)"
                    results.append(
                        (display, full_value, self.COLORS[5], 5, trigger)
                    )
                    seen.add(trigger)
                    if len(results) >= limit:
                        break

        if len(results) >= limit:
            return results[:limit]

        # 3. Prefix & Fuzzy Search
        candidates_to_fetch = []

        if len(target_fragment) >= 1:
            needed = limit - len(results)

            # Prefix Search in RAM (Fast, preserves popularity order)
            # Since self._tags_names is sorted by count DESC, the first
            # matches are the best.
            count_found = 0
            for name in self._tags_names:
                if name.startswith(target_fragment):
                    if name in seen:
                        continue
                    candidates_to_fetch.append(name)
                    seen.add(name)
                    count_found += 1
                    if count_found >= needed:
                        break

            # Fuzzy Search (only if needed and available)
            if (
                RAPIDFUZZ_AVAILABLE
                and len(results) + len(candidates_to_fetch) < limit
                and len(target_fragment) >= 3
            ):
                fuzzy_hits = process.extract(
                    target_fragment,
                    self._tags_names,
                    scorer=fuzz.WRatio,
                    limit=limit * 2,
                    score_cutoff=65,
                )

                for match_name, score, idx in fuzzy_hits:
                    if len(results) + len(candidates_to_fetch) >= limit:
                        break
                    if match_name in seen:
                        continue
                    candidates_to_fetch.append(match_name)
                    seen.add(match_name)

        # 4. Hydrate Metadata (Optimized: Single SQL Batch Query)
        if candidates_to_fetch:
            self._hydrate_and_add_results(
                results, candidates_to_fetch, prefix_str
            )

        return results[:limit]

    def _search_bigrams(
        self, context_word, target_fragment, prefix_str, results, seen, limit
    ):
        """Fetches contextual bigram suggestions from DB."""
        try:
            # Efficient SQL query to replace the in-memory dictionary lookup
            # We use LIKE to filter by fragment directly in the DB
            query = (
                "SELECT next_word FROM bigram "
                "WHERE current_word = ? AND next_word LIKE ? || '%' "
                "ORDER BY score DESC LIMIT ?"
            )
            cursor = self._db.execute_sql(
                query, (context_word, target_fragment, limit)
            )

            for (sugg,) in cursor.fetchall():
                if sugg in seen:
                    continue

                full_value = f"{prefix_str} {sugg}"
                display = f"{sugg} (Context)"

                results.append((display, full_value, self.COLORS[99], 99, sugg))
                seen.add(sugg)

        except Exception as e:
            logger.error(f"Bigram search failed: {e}")

    def search_middle_context(
        self, context_word, target_fragment, prefix_str, results, seen, limit
    ):
        """Fetches trigram sequences (Word1 -> Bridge -> Word2) where Word2
        starts with target_fragment."""
        try:
            # Optimization: We select only the bridge_word.
            # The 'WHERE' clause uses the primary key index for
            # head_word and tail_word.
            query = """
                SELECT DISTINCT head.next_word AS bridge_word
                FROM bigram AS head
                INNER JOIN bigram AS tail ON head.next_word = tail.current_word
                WHERE head.current_word = ? 
                  AND tail.next_word LIKE ? || '%'
                ORDER BY (head.score * tail.score) DESC 
                LIMIT ?
            """

            # execute_sql usually returns a cursor
            cursor = self._db.execute_sql(
                query, (context_word, target_fragment, limit)
            )

            for (bridge_word,) in cursor.fetchall():
                if bridge_word in seen:
                    continue

                # full_value is the reconstruction of the chain for the UI
                full_value = f"{prefix_str} {bridge_word}"
                display = f"{bridge_word} (Context)"

                # Using a priority constant for the magic number 99
                CONTEXT_PRIORITY = 99
                results.append(
                    (
                        display,
                        full_value,
                        self.COLORS[CONTEXT_PRIORITY],
                        CONTEXT_PRIORITY,
                        bridge_word,
                    )
                )
                seen.add(bridge_word)

        except Exception as e:
            logger.error(f"Contextual bigram search failed: {e}")

    def _hydrate_and_add_results(self, results, names, prefix_str):
        """Fetches metadata for candidates in batch and adds to results."""
        if not names:
            return

        try:
            # Create placeholders for IN clause
            placeholders = ",".join(["?"] * len(names))
            query = (
                "SELECT name, category, count FROM tag WHERE name "
                f"IN ({placeholders})"
            )

            cursor = self._db.execute_sql(query, names)

            # Map results for O(1) lookup
            meta_map = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            # Add to results in the original order of 'names' (which
            # preserves relevance)
            for name in names:
                cat, count = meta_map.get(name, (0, 0))  # Default if not found

                full_value = f"{prefix_str} {name}" if prefix_str else name
                display = f"{name} ({self._format_pop(count)})"
                color = self.COLORS.get(cat, "#ffffff")

                results.append((display, full_value, color, cat, name))

        except Exception as e:
            logger.error(f"Metadata hydration failed: {e}")

    def _format_pop(self, count: int) -> str:
        """Formats popularity count (e.g. 1.2M, 50k)."""
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        if count >= 1_000:
            return f"{count / 1_000:.0f}k"
        return str(count)

    def get_next_prob(self, current_word, limit=5):
        """
        Calculates the probability of next_words following the current_word.
        """
        query = """
            SELECT next_word, 
                   score / SUM(score) OVER() as probability
            FROM bigram
            WHERE current_word = ?
            ORDER BY score DESC
            LIMIT ?
        """
        cursor = self._db.execute_sql(query, (current_word, limit))
        return cursor.fetchall()

    def get_previous_prob(self, next_word, limit=5):
        """
        Calculates the probability of words preceding the next_word.
        """
        query = """
            SELECT current_word, 
                   score / SUM(score) OVER() as probability
            FROM bigram
            WHERE next_word = ?
            ORDER BY score DESC
            LIMIT ?
        """
        cursor = self._db.execute_sql(query, (next_word, limit))
        return cursor.fetchall()

    def get_common_collocations(self, multiplier=5.0, limit=20):
        """
        Finds bigrams with scores significantly higher than the
        global average.
        """
        query = """
            SELECT current_word, next_word, score
            FROM bigram
            WHERE score > (SELECT AVG(score) * ? FROM bigram)
            ORDER BY score DESC
            LIMIT ?
        """
        cursor = self._db.execute_sql(query, (multiplier, limit))
        return cursor.fetchall()

    def get_sentence_terminators(self, limit=10):
        """Finds words that frequently end sequences (no outgoing bigrams)."""
        query = """
            SELECT next_word, COUNT(*) as frequency
            FROM bigram
            WHERE next_word NOT IN (SELECT DISTINCT current_word FROM bigram)
            GROUP BY next_word
            ORDER BY frequency DESC
            LIMIT ?
        """
        cursor = self._db.execute_sql(query, (limit,))
        return cursor.fetchall()

    def suggest_trigrams(self, seed_word, limit=10):
        """
        Reconstructs 3-word sequences (Word1 -> Word2 -> Word3)
        using self-joins."""
        query = """
            SELECT 
                head.current_word, 
                head.next_word, 
                tail.next_word,
                (head.score * tail.score) AS confidence
            FROM bigram AS head
            INNER JOIN bigram AS tail ON head.next_word = tail.current_word
            WHERE head.current_word = ?
            ORDER BY confidence DESC
            LIMIT ?
        """
        cursor = self._db.execute_sql(query, (seed_word, limit))
        for w1, w2, w3, conf in cursor.fetchall():
            yield {
                "token": w1,
                "next": f"{w2} {w3}",
                "confidence": conf,
            }

    def get_bridge_words(self, word1, word2, limit=5):
        """
        Finds words that bridge word1 and word2 (Word1 -> Bridge -> Word2).
        """
        query = """
            SELECT DISTINCT head.next_word,
                   (head.score * tail.score) as score
            FROM bigram AS head
            INNER JOIN bigram AS tail ON head.next_word = tail.current_word
            WHERE head.current_word = ? 
              AND tail.next_word = ?
            ORDER BY score DESC 
            LIMIT ?
        """
        cursor = self._db.execute_sql(query, (word1, word2, limit))
        return cursor.fetchall()

    def __del__(self):
        """Closes DB connection on cleanup."""
        if self._db and not self._db.is_closed():
            self._db.close()

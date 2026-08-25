"""Reading triggers from the c-chain indexer.

The DAL grows **no chain indexer of its own**. Triggers come from the shared
c-chain indexer's database and all *state* is read from the contracts directly
over RPC at latest, which is why no historical registry is needed either.

Deliberately **not** a Django database alias. The indexer's schema is managed by
gorm in another repository and Django must never migrate, own, or create it --
and an alias would invite exactly that, because `migrate` walks every alias and
the test runner creates a test database for each one. A plain read-only client
keeps the boundary where it belongs.

Two things this reader must get right, and both are about **absence**:

* An indexer that is behind returns exactly what a chain on which nothing
  happened returns. Every answer therefore carries the window it was taken
  from, so a caller cannot mistake lag for silence.
* An indexer keeps a bounded history -- roughly a week in the deployment this
  targets. A query reaching further back than the floor is not empty, it is
  **unanswerable**, and saying so is the difference between "no trigger existed"
  and "the log that proves one existed has been dropped".
"""

import logging
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Final

import pymysql
from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)

__all__ = [
    "HistoryGap",
    "ImproperlyConfiguredIndexer",
    "IndexerReader",
    "LogRow",
    "Window",
    "from_settings",
]

# States the indexer maintains. The strings are a wire contract with it.
CHAIN_TIP: Final = "last_chain_block"
LAST_INDEXED: Final = "last_database_block"
BLOCK_FLOOR: Final = "first_database_block"
LOG_FLOOR: Final = "first_database_log_block"


class ImproperlyConfiguredIndexer(Exception):
    """The indexer connection is not configured."""


class HistoryGap(Exception):
    """The range asked about is older than the indexer still holds.

    Never an empty result: an empty result means "nothing happened", and these
    two must not be confused by anything that decides whether an expectation
    exists.
    """


@dataclass(frozen=True, slots=True)
class Window:
    """What the indexer could answer about, at the moment it was asked."""

    chain_tip: int
    last_indexed: int
    log_floor: int

    @property
    def lag(self) -> int:
        """Blocks between the chain's tip and what has been written."""
        return max(0, self.chain_tip - self.last_indexed)

    def covers(self, from_block: int) -> bool:
        return from_block >= self.log_floor


@dataclass(frozen=True, slots=True)
class LogRow:
    """One log, with hex fields exactly as the indexer stores them.

    Lowercase, and **without** an ``0x`` prefix -- the indexer writes
    ``Hex()[2:]``. Nothing here re-prefixes them: a caller comparing against a
    prefixed literal should fail loudly rather than silently match nothing.
    """

    address: str
    topic0: str
    topic1: str
    topic2: str
    topic3: str
    data: str
    transaction_hash: str
    log_index: int
    block_number: int
    timestamp: int


class IndexerReader:
    """A read-only client for the c-chain indexer's store."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        connect_timeout: int = 5,
    ):
        self._connect_args = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
            "connect_timeout": connect_timeout,
            "read_timeout": connect_timeout * 2,
            "cursorclass": DictCursor,
            "autocommit": True,
        }

    @contextmanager
    def _cursor(self):
        connection = pymysql.connect(**self._connect_args)
        try:
            with connection.cursor() as cursor:
                yield cursor
        finally:
            connection.close()

    def window(self) -> Window:
        """What the indexer currently holds, and how far behind the chain it is."""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT name, `index` FROM states WHERE name IN (%s, %s, %s, %s)",
                (CHAIN_TIP, LAST_INDEXED, BLOCK_FLOOR, LOG_FLOOR),
            )
            rows = {row["name"]: int(row["index"]) for row in cursor.fetchall()}

        # A missing state row means an indexer that has not finished starting.
        # Reporting zeros would claim a floor of zero -- that the indexer holds
        # all history -- which is the one wrong answer that fails silently.
        missing = {CHAIN_TIP, LAST_INDEXED} - rows.keys()
        if missing:
            raise HistoryGap(
                f"indexer has not published {', '.join(sorted(missing))} yet"
            )

        return Window(
            chain_tip=rows[CHAIN_TIP],
            last_indexed=rows[LAST_INDEXED],
            # The log floor is absent when nothing has been dropped; the block
            # floor is the next best answer, and zero only if neither exists.
            log_floor=rows.get(LOG_FLOOR, rows.get(BLOCK_FLOOR, 0)),
        )

    def logs(
        self,
        *,
        address: str,
        topic0: str,
        from_block: int,
        to_block: int | None = None,
        limit: int = 1000,
    ) -> tuple[Sequence[LogRow], Window]:
        """Logs of one event from one contract, with the window they came from.

        Returns the window alongside the rows on purpose: an empty result is
        only meaningful next to how far the indexer has actually written.
        """
        window = self.window()
        if not window.covers(from_block):
            raise HistoryGap(
                f"block {from_block} is below the indexer's log floor "
                f"{window.log_floor}; those logs have been dropped"
            )

        upper = (
            window.last_indexed
            if to_block is None
            else min(to_block, window.last_indexed)
        )
        if upper < from_block:
            # Not an error: the indexer simply has not reached this range yet.
            return (), window

        with self._cursor() as cursor:
            cursor.execute(
                "SELECT address, topic0, topic1, topic2, topic3, data,"
                " transaction_hash, log_index, block_number, timestamp"
                " FROM logs"
                " WHERE address = %s AND topic0 = %s"
                " AND block_number >= %s AND block_number <= %s"
                " ORDER BY block_number, log_index"
                " LIMIT %s",
                (_bare(address), _bare(topic0), from_block, upper, limit),
            )
            rows = [
                LogRow(
                    address=row["address"],
                    topic0=row["topic0"],
                    topic1=row["topic1"],
                    topic2=row["topic2"],
                    topic3=row["topic3"],
                    data=row["data"],
                    transaction_hash=row["transaction_hash"],
                    log_index=int(row["log_index"]),
                    block_number=int(row["block_number"]),
                    timestamp=int(row["timestamp"]),
                )
                for row in cursor.fetchall()
            ]

        if not rows:
            logger.debug(
                "DAL: no %s logs from %s in [%d, %d]; indexer lag %d block(s)",
                topic0[:10],
                address,
                from_block,
                upper,
                window.lag,
            )
        return rows, window


def _bare(value: str) -> str:
    """Lowercase, unprefixed hex -- the form the indexer stores.

    Applied to inputs rather than to stored rows: a query written with an
    ``0x``-prefixed address would otherwise match nothing at all, and matching
    nothing is indistinguishable from a contract that never emitted.
    """
    return value.removeprefix("0x").removeprefix("0X").lower()


def from_settings() -> IndexerReader:
    """Build a reader from ``settings.CCHAIN_INDEXER``.

    Fails loudly on a missing host rather than defaulting to localhost: a
    reader pointed at nothing returns empty answers, and an empty answer from
    this service means "no trigger existed".
    """
    from django.conf import settings

    config = settings.CCHAIN_INDEXER
    if not config.get("HOST") or not config.get("NAME"):
        raise ImproperlyConfiguredIndexer(
            "CCHAIN_DB_HOST and CCHAIN_DB_NAME must be set: without them the "
            "DAL reads no triggers and reports it as a quiet chain"
        )
    return IndexerReader(
        host=config["HOST"],
        port=int(config["PORT"]),
        database=config["NAME"],
        user=config["USER"],
        password=config["PASSWORD"],
    )

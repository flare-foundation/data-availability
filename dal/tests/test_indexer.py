"""The c-chain indexer reader, against a real MySQL holding the real schema.

The schema under these tests is created by the indexer's OWN gorm migrator, not
transcribed here, so a fixture cannot drift from the thing it stands in for. If
`CCHAIN_DB_HOST` is unset the module skips: the tests are worth running, and a
machine without MySQL should not be told the reader is broken.

What they are really about is **absence**. An indexer that is behind and a chain
on which nothing happened return the same empty list, and an indexer that has
dropped its history returns the same empty list again. Three different facts,
one wire answer, and only the first is safe to act on.
"""

import os

import pytest

pymysql = pytest.importorskip("pymysql")

from dal.chain.indexer import (  # noqa: E402
    BLOCK_FLOOR,
    CHAIN_TIP,
    LAST_INDEXED,
    LOG_FLOOR,
    HistoryGap,
    IndexerReader,
)

HOST = os.environ.get("CCHAIN_DB_HOST")
PORT = int(os.environ.get("CCHAIN_DB_PORT", "3306"))
NAME = os.environ.get("CCHAIN_DB_NAME", "flare_csp_indexer")
USER = os.environ.get("CCHAIN_DB_USER", "root")
PASSWORD = os.environ.get("CCHAIN_DB_PASSWORD", "")


def _reachable() -> bool:
    """Skip on "configured but not running", not only on "not configured".

    A host that is set and unreachable is the ordinary state of a developer
    machine between harness runs, and reporting it as a failure teaches people
    to ignore red — which costs more than the coverage these tests add.
    """
    if not HOST:
        return False
    try:
        pymysql.connect(
            host=HOST,
            port=PORT,
            database=NAME,
            user=USER,
            password=PASSWORD,
            connect_timeout=2,
        ).close()
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _reachable(),
    reason="no c-chain indexer database reachable; set CCHAIN_DB_HOST and start one",
)

ADDRESS = "1234567890abcdef1234567890abcdef12345678"
TOPIC = "ab" * 32
OTHER_TOPIC = "cd" * 32


@pytest.fixture
def raw():
    connection = pymysql.connect(
        host=HOST,
        port=PORT,
        database=NAME,
        user=USER,
        password=PASSWORD,
        autocommit=True,
    )
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def indexer(raw):
    """A clean slate in the real schema, restored after each test."""
    with raw.cursor() as cursor:
        cursor.execute("DELETE FROM logs")
        cursor.execute("DELETE FROM states")
    yield IndexerReader(
        host=HOST, port=PORT, database=NAME, user=USER, password=PASSWORD
    )
    with raw.cursor() as cursor:
        cursor.execute("DELETE FROM logs")
        cursor.execute("DELETE FROM states")


def set_state(raw, name, index, timestamp=0):
    with raw.cursor() as cursor:
        cursor.execute(
            "INSERT INTO states (name, `index`, block_timestamp, updated)"
            " VALUES (%s, %s, %s, NOW())"
            " ON DUPLICATE KEY UPDATE `index` = VALUES(`index`)",
            (name, index, timestamp),
        )


def add_log(raw, *, block, log_index=0, address=ADDRESS, topic0=TOPIC, data="00"):
    with raw.cursor() as cursor:
        cursor.execute(
            "INSERT INTO logs (address, data, topic0, topic1, topic2, topic3,"
            " transaction_hash, log_index, timestamp, block_number)"
            " VALUES (%s, %s, %s, '', '', '', %s, %s, %s, %s)",
            (address, data, topic0, f"{block:064x}", log_index, block * 10, block),
        )


class TestWindow:
    def test_an_indexer_that_has_not_started_is_not_an_empty_chain(self, indexer):
        # No state rows at all. Reporting zeros would claim a floor of zero --
        # that the indexer holds ALL history -- which is the one wrong answer
        # that fails silently.
        with pytest.raises(HistoryGap, match="has not published"):
            indexer.window()

    def test_the_window_reports_lag(self, raw, indexer):
        set_state(raw, CHAIN_TIP, 1000)
        set_state(raw, LAST_INDEXED, 940)
        window = indexer.window()
        assert (window.chain_tip, window.last_indexed, window.lag) == (1000, 940, 60)

    def test_the_log_floor_is_preferred_over_the_block_floor(self, raw, indexer):
        set_state(raw, CHAIN_TIP, 1000)
        set_state(raw, LAST_INDEXED, 1000)
        set_state(raw, BLOCK_FLOOR, 100)
        set_state(raw, LOG_FLOOR, 300)
        assert indexer.window().log_floor == 300

    def test_no_floor_at_all_means_nothing_has_been_dropped(self, raw, indexer):
        set_state(raw, CHAIN_TIP, 50)
        set_state(raw, LAST_INDEXED, 50)
        assert indexer.window().log_floor == 0


class TestLogs:
    @pytest.fixture(autouse=True)
    def _tip(self, raw, indexer):
        # Depends on `indexer` so it runs AFTER the clean slate, not before it.
        set_state(raw, CHAIN_TIP, 1000)
        set_state(raw, LAST_INDEXED, 1000)

    def test_logs_come_back_in_chain_order(self, raw, indexer):
        add_log(raw, block=20, log_index=1)
        add_log(raw, block=10, log_index=5)
        add_log(raw, block=20, log_index=0)

        rows, _ = indexer.logs(address=ADDRESS, topic0=TOPIC, from_block=0)
        assert [(r.block_number, r.log_index) for r in rows] == [
            (10, 5),
            (20, 0),
            (20, 1),
        ]

    def test_a_prefixed_address_still_matches(self, raw, indexer):
        # The indexer stores bare lowercase hex. A caller passing the 0x form
        # would otherwise match nothing, and matching nothing is
        # indistinguishable from a contract that never emitted.
        add_log(raw, block=10)
        rows, _ = indexer.logs(
            address="0x" + ADDRESS.upper(), topic0="0x" + TOPIC.upper(), from_block=0
        )
        assert len(rows) == 1

    def test_another_event_from_the_same_contract_is_not_returned(self, raw, indexer):
        add_log(raw, block=10, topic0=OTHER_TOPIC)
        rows, _ = indexer.logs(address=ADDRESS, topic0=TOPIC, from_block=0)
        assert rows == () or list(rows) == []

    def test_dropped_history_raises_rather_than_answering_empty(self, raw, indexer):
        # THE case this reader exists for. Asking below the floor is not "no
        # trigger existed" -- it is "the log that would prove one existed has
        # been deleted", and a collector must not create or skip expectations on
        # the strength of it.
        set_state(raw, LOG_FLOOR, 500)
        with pytest.raises(HistoryGap, match="log floor"):
            indexer.logs(address=ADDRESS, topic0=TOPIC, from_block=100)

    def test_a_range_ahead_of_the_indexer_is_empty_not_an_error(self, raw, indexer):
        # The indexer simply has not got there yet. Retryable, and the window
        # says so.
        set_state(raw, LAST_INDEXED, 40)
        rows, window = indexer.logs(address=ADDRESS, topic0=TOPIC, from_block=100)
        assert list(rows) == []
        assert window.last_indexed == 40

    def test_the_query_never_reads_past_what_was_written(self, raw, indexer):
        # A log can exist in a block the indexer has not yet finished writing
        # through. Returning it would let a caller act on a block that may still
        # be rewritten.
        set_state(raw, LAST_INDEXED, 15)
        add_log(raw, block=10)
        add_log(raw, block=20)
        rows, _ = indexer.logs(address=ADDRESS, topic0=TOPIC, from_block=0)
        assert [r.block_number for r in rows] == [10]

    def test_every_answer_carries_its_window(self, raw, indexer):
        # An empty list is only meaningful beside how far the indexer has
        # actually written. Returning them together is what stops a caller
        # reading lag as silence.
        rows, window = indexer.logs(address=ADDRESS, topic0=TOPIC, from_block=0)
        assert list(rows) == []
        assert window.last_indexed == 1000

    def test_fields_are_returned_as_stored(self, raw, indexer):
        add_log(raw, block=10, data="deadbeef")
        (row,), _ = indexer.logs(address=ADDRESS, topic0=TOPIC, from_block=0)
        assert row.address == ADDRESS
        assert row.topic0 == TOPIC
        assert row.data == "deadbeef"
        assert not row.address.startswith("0x")

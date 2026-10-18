from wordle_bot.db import Result, has_any, latest_wordle_no, upsert_results, user_results

G = 1


def test_upsert_and_read(conn, summary_lines):
    upsert_results(conn, G, 1942, summary_lines, channel_id=10, message_id=20)
    assert user_results(conn, G, 111) == [Result(1942, 4, True)]
    assert user_results(conn, G, 444)[0].guesses is None


def test_upsert_is_idempotent(conn, summary_lines):
    upsert_results(conn, G, 1942, summary_lines, channel_id=10, message_id=20)
    upsert_results(conn, G, 1942, summary_lines, channel_id=11, message_id=21)
    assert conn.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 4


def test_latest_wordle_no(conn, summary_lines):
    assert latest_wordle_no(conn, G) is None
    assert not has_any(conn, G)
    upsert_results(conn, G, 1940, summary_lines, channel_id=10, message_id=20)
    upsert_results(conn, G, 1942, summary_lines, channel_id=10, message_id=21)
    assert latest_wordle_no(conn, G) == 1942
    assert has_any(conn, G)


def test_guilds_isolated(conn, summary_lines):
    upsert_results(conn, 1, 1942, summary_lines, channel_id=10, message_id=20)
    assert user_results(conn, 2, 111) == []
    assert not has_any(conn, 2)


def test_guild_results(conn, summary_lines):
    from wordle_bot.db import guild_results
    upsert_results(conn, G, 1942, summary_lines, channel_id=10, message_id=20)
    by_user = guild_results(conn, G)
    assert set(by_user) == {111, 222, 333, 444}
    assert by_user[333] == [Result(1942, 6, False)]


def test_latest_message_id(conn, summary_lines):
    from wordle_bot.db import latest_message_id
    assert latest_message_id(conn, G) is None
    upsert_results(conn, G, 1940, summary_lines, channel_id=10, message_id=500)
    upsert_results(conn, G, 1941, summary_lines, channel_id=10, message_id=900)
    assert latest_message_id(conn, G) == 900


def test_backfill_complete_marker(conn):
    from wordle_bot.db import backfill_complete, mark_backfill_complete
    assert not backfill_complete(conn, G)
    mark_backfill_complete(conn, G)
    mark_backfill_complete(conn, G)
    assert backfill_complete(conn, G)
    assert not backfill_complete(conn, 2)


def test_answer_cache_roundtrip(conn):
    from wordle_bot.db import cached_answers, store_answer
    store_answer(conn, 1936, "PROVE")
    assert cached_answers(conn, [1936, 1937]) == {1936: "PROVE"}

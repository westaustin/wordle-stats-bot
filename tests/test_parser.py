from datetime import datetime, timezone

from wordle_bot.parser import is_summary, parse_summary, wordle_number_for

SUMMARY = ("Wordle: Your group is on a 432 day streak! 🔥🔥🔥 Here are yesterday's results:\n"
           "👑 4/6: <@111> <@222>\n6/6: <@333>\nX/6: <@444>")


def test_is_summary():
    assert is_summary(SUMMARY)
    assert not is_summary("Wordle: \nSlicck was playing")


def test_parse_lines():
    s = parse_summary(SUMMARY)
    assert [(l.guesses, l.crown, l.user_ids) for l in s.lines] == [
        (4, True, [111, 222]), (6, False, [333]), (None, False, [444])]
    assert s.skipped == []


def test_parse_nickname_mentions():
    s = parse_summary("Here are yesterday's results:\n3/6: <@!555>")
    assert s.lines[0].user_ids == [555]


def test_parse_skips_garbage_line():
    s = parse_summary("Here are yesterday's results:\n7/6: <@1>\n2/6: <@2>")
    assert [l.guesses for l in s.lines] == [2]
    assert s.skipped == ["7/6: <@1>"]


def test_wordle_number_known_day():
    assert wordle_number_for(datetime(2026, 10, 18, 14, 0, tzinfo=timezone.utc)) == 1946


def test_wordle_number_uses_eastern_time():
    # 03:30 UTC on 10-18 is 23:30 ET on 10-17, so "yesterday" is 10-16
    assert wordle_number_for(datetime(2026, 10, 18, 3, 30, tzinfo=timezone.utc)) == 1945


def test_parse_plain_text_names():
    s = parse_summary("Here are yesterday's results:\n👑 3/6: @OnlyTees\n"
                      "4/6: @snowMAMA @That Good Kwat @Slicck\n5/6: <@111> @Bob")
    assert [(l.guesses, l.user_ids, l.names) for l in s.lines] == [
        (3, [], ["OnlyTees"]), (4, [], ["snowMAMA", "That Good Kwat", "Slicck"]), (5, [111], ["Bob"])]
    assert s.skipped == []

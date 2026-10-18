import pytest

from wordle_bot.db import connect
from wordle_bot.parser import parse_summary

SUMMARY = ("Wordle: Your group is on a 432 day streak! 🔥🔥🔥 Here are yesterday's results:\n"
           "👑 4/6: <@111> <@222>\n6/6: <@333>\nX/6: <@444>")


@pytest.fixture
def conn(tmp_path):
    c = connect(str(tmp_path / "test.db"))
    yield c
    c.close()


@pytest.fixture
def summary_lines():
    return parse_summary(SUMMARY).lines

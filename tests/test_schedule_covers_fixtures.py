"""Does the schedule actually catch the football?

Four hardcoded cron slots looked reasonable and covered 119 of 361 remaining
fixtures -- because Premier League kickoffs land on ten different UTC times
across a season, the UK leaves BST in October, and the workflow's cron is a
fixed UTC string. The live product would have sat idle for most of the season
and nothing would have said so.

So the pairing is checked rather than assumed: the cron expression is read out
of the workflow, the kickoff times out of the committed fixture list, and every
remaining fixture is simulated against them. Both inputs are in the repository,
so this runs in CI.
"""
import datetime as dt
import json
import os
import re

import pytest

HERE = os.path.dirname(__file__)
WORKFLOW = os.path.join(HERE, "..", ".github", "workflows", "matchday.yml")
FIXTURES = os.path.join(HERE, "..", "docs", "fixtures.json")

MATCH_MINUTES = 105        # kickoff to final whistle, with stoppages


def fire_hours():
    """The UTC hours the matchday workflow fires, from its own cron line."""
    text = open(WORKFLOW).read()
    crons = re.findall(r'- cron:\s*"([^"]+)"', text)
    assert crons, "no cron found in the matchday workflow"
    hours, minutes = set(), set()
    for c in crons:
        minute, hour = c.split()[0], c.split()[1]
        minutes.add(int(minute))
        for part in hour.split(","):
            if "-" in part:
                a, b = part.split("-")
                hours.update(range(int(a), int(b) + 1))
            else:
                hours.add(int(part))
    assert len(minutes) == 1, f"mixed firing minutes {minutes}; update this test"
    return sorted(hours), minutes.pop()


def settings():
    """KICKOFF_WINDOW and the poll length the workflow actually passes."""
    import sys
    sys.path.insert(0, os.path.join(HERE, "..", "src"))
    import publish
    text = open(WORKFLOW).read()
    m = re.search(r"inputs\.minutes \|\| '(\d+)'", text)
    return publish.KICKOFF_WINDOW, float(m.group(1)) if m else 165.0


def upcoming():
    if not os.path.exists(FIXTURES):
        pytest.skip("no fixtures.json; run src/fixtures.py")
    fx = json.load(open(FIXTURES)).get("fixtures", [])
    return [f for f in fx if not f.get("completed")]


def minutes_of_match_missed(kickoff, hours, minute, window, poll):
    """Least of the match any firing would miss. None if never caught."""
    best = None
    for h in hours:
        for day in (-1, 0):
            fire = kickoff.replace(hour=h, minute=minute, second=0,
                                   microsecond=0) + dt.timedelta(days=day)
            gap = (kickoff - fire).total_seconds() / 60
            if gap < -MATCH_MINUTES or gap > poll:
                continue                       # job finished, or not started
            if gap > window and gap >= 0:
                continue                       # goes back to sleep too early
            missed = max(0.0, -gap)
            best = missed if best is None else min(best, missed)
    return best


def test_every_remaining_fixture_is_caught_from_kickoff():
    fx = upcoming()
    hours, minute = fire_hours()
    window, poll = settings()

    missed, late = [], []
    for f in fx:
        ko = dt.datetime.fromisoformat(f["kickoff"].replace("Z", "+00:00"))
        got = minutes_of_match_missed(ko, hours, minute, window, poll)
        label = f"{f['kickoff']} {f['home']} v {f['away']}"
        if got is None:
            missed.append(label)
        elif got > 1:
            late.append(f"{label} (+{got:.0f} min)")

    assert not missed, (
        f"{len(missed)} of {len(fx)} fixtures never caught, e.g. {missed[:3]}")
    assert not late, (
        f"{len(late)} fixtures caught mid-match, e.g. {late[:3]}")


def test_the_waiting_window_reaches_the_next_kickoff():
    """A firing on :50 must be able to wait for a :30 kickoff, forty minutes
    later. This is the constant the earlier version got wrong."""
    hours, minute = fire_hours()
    window, _ = settings()
    worst = max((60 - minute) % 60, (30 - minute) % 60)
    assert window >= worst, (
        f"firing at :{minute:02d} with a {window}-minute window cannot reach a "
        f"kickoff {worst} minutes later")


def test_the_poll_outlasts_a_match():
    window, poll = settings()
    assert poll >= window + MATCH_MINUTES, (
        f"waiting up to {window} min then polling leaves {poll - window:.0f} "
        f"min for a {MATCH_MINUTES}-minute match")

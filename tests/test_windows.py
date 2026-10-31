from datetime import date, datetime, timezone

import pytest

from pipeline.study.windows import (
    PERIODS,
    PRIMEIRO_TURNO,
    SEGUNDO_TURNO,
    day_offset,
    event_window,
    local_day,
    period_of,
)


def test_periods_do_not_overlap_and_are_ordered():
    for a, b in zip(PERIODS, PERIODS[1:]):
        assert a.end is not None and a.end < b.start


def test_election_days_stay_in_the_period_that_ends_on_them():
    assert period_of(PRIMEIRO_TURNO) == "campanha_1t"
    assert period_of(date(2026, 10, 5)) == "entre_turnos"
    assert period_of(SEGUNDO_TURNO) == "entre_turnos"
    assert period_of(date(2026, 10, 26)) == "pos_eleicao"
    assert period_of(date(2027, 3, 1)) == "pos_eleicao"  # período em aberto


def test_period_of_returns_none_outside_all_periods():
    assert period_of(date(2026, 1, 1)) is None


def test_event_window_and_offset():
    start, end = event_window(SEGUNDO_TURNO, before=14, after=14)
    assert (start, end) == (date(2026, 10, 11), date(2026, 11, 8))
    assert day_offset(SEGUNDO_TURNO, SEGUNDO_TURNO) == 0
    assert day_offset(date(2026, 10, 20), SEGUNDO_TURNO) == -5


def test_local_day_uses_brazil_time_not_utc():
    # 01:30 UTC de 26/10 = 22:30 de 25/10 em Brasília (UTC-3)
    assert local_day(datetime(2026, 10, 26, 1, 30, tzinfo=timezone.utc)) == date(2026, 10, 25)
    assert local_day(datetime(2026, 10, 26, 3, 0, tzinfo=timezone.utc)) == date(2026, 10, 26)


def test_local_day_rejects_naive_datetimes():
    with pytest.raises(ValueError):
        local_day(datetime(2026, 10, 26, 1, 30))

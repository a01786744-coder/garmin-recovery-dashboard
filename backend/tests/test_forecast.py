# v5.3 F1: tomorrow's recovery forecast.
from backend import forecast as fc


def _day(date, rec=None, strain=None, acwr=None, hrv=None,
         need=480, actual=480):
    return {"date": date, "recovery_score": rec, "strain_score": strain,
            "acwr_ratio": acwr, "hrv_last_night": hrv,
            "sleep_need_baseline": need, "sleep_need_actual": actual}


def _week(**today):
    # 7 calm baseline days (recovery ~60, easy strain) + a configurable today.
    rows = [_day(f"2026-07-{10+i:02d}", rec=60, strain=8, acwr=1.0, hrv=60)
            for i in range(7)]
    rows.append(_day("2026-07-17", **today))
    return rows


def test_calm_day_forecasts_near_baseline():
    f = fc.forecast_recovery(_week(rec=60, strain=8, acwr=1.0, hrv=60))
    assert f is not None
    assert 54 <= f["point"] <= 66           # reverts toward the recent norm
    assert f["low"] < f["point"] < f["high"]
    assert f["band"] in ("green", "yellow", "red")


def test_hard_strain_lowers_forecast():
    calm = fc.forecast_recovery(_week(rec=60, strain=8, acwr=1.0, hrv=60))
    hard = fc.forecast_recovery(_week(rec=60, strain=80, acwr=1.0, hrv=60))
    assert hard["point"] < calm["point"] - 3
    assert any("strain" in d["label"].lower() and d["effect"] < 0 for d in hard["drivers"])


def test_sleep_debt_lowers_forecast():
    rested = _week(rec=60, strain=8, acwr=1.0, hrv=60)
    indebted = [dict(r, sleep_need_actual=r["sleep_need_baseline"] - 90)
                for r in rested]                     # 90 min short every night
    a = fc.forecast_recovery(rested)["point"]
    b = fc.forecast_recovery(indebted)["point"]
    assert b < a - 2
    assert any("debt" in d["label"].lower() for d in fc.forecast_recovery(indebted)["drivers"])


def test_high_acwr_lowers_forecast():
    lo = fc.forecast_recovery(_week(rec=60, strain=8, acwr=1.0, hrv=60))
    hi = fc.forecast_recovery(_week(rec=60, strain=8, acwr=1.6, hrv=60))
    assert hi["point"] < lo["point"] - 2
    assert any("load" in d["label"].lower() for d in hi["drivers"])


def test_hrv_trend_direction():
    rising = [_day(f"2026-07-{10+i:02d}", rec=60, strain=8, acwr=1.0, hrv=52 + 2 * i)
              for i in range(8)]
    falling = [_day(f"2026-07-{10+i:02d}", rec=60, strain=8, acwr=1.0, hrv=68 - 2 * i)
               for i in range(8)]
    assert fc.forecast_recovery(rising)["point"] > fc.forecast_recovery(falling)["point"]


def test_sleep_range_brackets_point():
    f = fc.forecast_recovery(_week(rec=55, strain=30, acwr=1.1, hrv=58))
    assert f["high"] - f["low"] >= 8        # tonight's sleep matters
    assert 0 <= f["low"] <= f["point"] <= f["high"] <= 100


def test_drivers_sorted_by_magnitude():
    f = fc.forecast_recovery(_week(rec=60, strain=85, acwr=1.6, hrv=60))
    effects = [abs(d["effect"]) for d in f["drivers"]]
    assert effects == sorted(effects, reverse=True)
    assert all(d["effect"] != 0 for d in f["drivers"])


def test_insufficient_history_returns_none():
    assert fc.forecast_recovery([]) is None
    assert fc.forecast_recovery([_day("2026-07-17", rec=60, strain=8)]) is None  # 1 day

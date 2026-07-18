# backend/tests/test_recovery.py
import backend.recovery as r

def test_neutral_day_near_58():
    hist_hrv = [40] * 30
    hist_rhr = [50] * 30
    # today equals baseline mean → sigmoid(+0.3) ≈ 57-58
    assert 55 <= r.recovery_score(40, 50, hist_hrv, hist_rhr) <= 60

def test_high_hrv_low_rhr_is_green():
    hist_hrv = list(range(30, 60))       # mean ~44, std ~8.6
    hist_rhr = list(range(45, 75))
    score = r.recovery_score(70, 44, hist_hrv, hist_rhr)
    assert score >= 67
    assert r.recovery_band(score) == "green"

def test_low_hrv_high_rhr_is_red():
    hist_hrv = list(range(30, 60))
    hist_rhr = list(range(45, 75))
    score = r.recovery_score(25, 80, hist_hrv, hist_rhr)
    assert score <= 33
    assert r.recovery_band(score) == "red"

def test_hrv_weight_shifts_the_blend():
    # HRV strongly positive, RHR strongly negative. Weighting HRV higher must
    # raise the score; weighting RHR higher must lower it.
    hist_hrv = list(range(30, 60))
    hist_rhr = list(range(45, 75))
    hi = r.recovery_score(70, 80, hist_hrv, hist_rhr, hrv_weight=0.9)
    lo = r.recovery_score(70, 80, hist_hrv, hist_rhr, hrv_weight=0.1)
    assert hi > lo
    # explanation weights reflect the setting (rounded)
    ex = r.recovery_explanation(70, 80, hist_hrv, hist_rhr, hrv_weight=0.6)
    assert ex["weights"] == {"hrv": 0.6, "rhr": 0.4}


def test_recovery_band_custom_cutoffs():
    assert r.recovery_band(65, green=60, amber=30) == "green"   # would be yellow at defaults
    assert r.recovery_band(45, green=60, amber=40) == "yellow"
    assert r.recovery_band(20, green=60, amber=40) == "red"


def test_insufficient_history_returns_none():
    assert r.recovery_score(40, 50, [40] * 10, [50] * 10) is None

def test_missing_today_returns_none():
    assert r.recovery_score(None, 50, [40] * 30, [50] * 30) is None

def test_strain_none_when_no_activities():
    assert r.strain_score([]) is None

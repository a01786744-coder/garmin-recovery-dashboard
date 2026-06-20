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

def test_insufficient_history_returns_none():
    assert r.recovery_score(40, 50, [40] * 10, [50] * 10) is None

def test_missing_today_returns_none():
    assert r.recovery_score(None, 50, [40] * 30, [50] * 30) is None

def test_strain_none_when_no_activities():
    assert r.strain_score([]) is None

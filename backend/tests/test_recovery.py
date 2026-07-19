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


# --- v5.1: multi-factor recovery ---

HRV_H = [40] * 30
RHR_H = [50] * 30

def _score(**extras):
    return r.recovery_score(40, 50, HRV_H, RHR_H, extras=extras or None)

def test_no_extras_matches_legacy_formula():
    # Without extras the autonomic core renormalizes to 100% — identical to
    # the historical 2-factor score.
    assert _score() == r.recovery_score(40, 50, HRV_H, RHR_H)

def test_good_sleep_raises_score():
    base = _score()
    good = _score(sleep_total_s=8 * 3600, sleep_need_min=480, sleep_score=92)
    short = _score(sleep_total_s=5 * 3600, sleep_need_min=480, sleep_score=55)
    assert good > base > short

def test_sleep_quality_alone_counts():
    # Duration/need missing -> quality carries the sleep block.
    assert _score(sleep_score=95) > _score() > _score(sleep_score=50)

def test_elevated_respiration_lowers_score():
    resp_h = [14.0] * 30
    assert _score(resp_today=17.0, resp_hist=resp_h) < _score()
    # Lower-than-baseline resp is capped: small boost at most.
    assert _score(resp_today=10.0, resp_hist=resp_h) <= _score() + 3

def test_skin_temp_deviation_only_penalizes():
    assert _score(skin_temp_dev=0.1) == _score()          # normal -> no effect
    assert _score(skin_temp_dev=1.3) < _score()           # feverish -> down
    assert _score(skin_temp_dev=-1.3) < _score()          # big drop -> down too

def test_spo2_drop_penalizes_high_never_boosts():
    spo2_h = [95.0] * 30
    assert _score(spo2_today=89.0, spo2_hist=spo2_h) < _score()
    assert _score(spo2_today=98.0, spo2_hist=spo2_h) == _score()

def test_explanation_reports_components_and_effective_weights():
    ex = r.recovery_explanation(40, 50, HRV_H, RHR_H, extras={
        "sleep_total_s": 7 * 3600, "sleep_need_min": 460, "sleep_score": 80,
        "resp_today": 14.5, "resp_hist": [14.0] * 30,
        "skin_temp_dev": 0.9,
        "spo2_today": 93.0, "spo2_hist": [95.0] * 30,
    })
    w = ex["weights"]
    assert set(w) == {"hrv", "rhr", "sleep", "resp", "temp", "spo2"}
    assert abs(sum(w.values()) - 1.0) < 0.02
    assert w["hrv"] > w["rhr"] > w["sleep"] / 2   # HRV stays dominant
    assert ex["sleep"]["total_min"] == 420 and ex["sleep"]["score"] == 80
    assert ex["resp"]["baseline"] == 14.0
    assert ex["temp"]["z"] < 0
    assert ex["spo2"]["z"] < 0

def test_missing_block_renormalizes():
    # Only sleep present as extra: weights sum to 1 over hrv/rhr/sleep.
    ex = r.recovery_explanation(40, 50, HRV_H, RHR_H,
                                extras={"sleep_score": 80})
    assert set(ex["weights"]) == {"hrv", "rhr", "sleep"}
    assert abs(sum(ex["weights"].values()) - 1.0) < 0.02


# --- v5.1: strain v2 ---

def test_strain_trimp_fallback_from_zones():
    acts = [{"activity_id": 9, "duration_s": 3600, "avg_hr": 150,
             "training_load": None}]
    zones = {9: [{"zoneNumber": 2, "secsInZone": 1200},
                 {"zoneNumber": 3, "secsInZone": 1800},
                 {"zoneNumber": 4, "secsInZone": 600}]}
    b = r.strain_breakdown(acts, None, zones_by_activity=zones)
    # Edwards TRIMP: 20*2 + 30*3 + 10*4 = 170
    assert b["workout"] == 170.0
    # zones beat the crude duration*HR fallback (which would be 90)
    crude = r.strain_breakdown(acts, None)
    assert crude["workout"] == 90.0

def test_strain_training_load_beats_zones():
    acts = [{"activity_id": 9, "training_load": 220}]
    zones = {9: [{"zoneNumber": 3, "secsInZone": 3600}]}
    assert r.strain_breakdown(acts, None, zones_by_activity=zones)["workout"] == 220

def test_strain_sedentary_steps_dont_count():
    low = r.strain_breakdown([], {"steps": 2500})
    assert low["daily"] == 0.0
    high = r.strain_breakdown([], {"steps": 12000})
    assert high["daily"] == 2.5 * 9.0   # only steps above 3000

def test_strain_counts_floors():
    b = r.strain_breakdown([], {"steps": 3000, "floors_ascended": 10})
    assert b["daily"] == 5.0

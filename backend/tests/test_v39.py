"""v3.9: full Forerunner 970 data integration. Payload shapes below are taken
from the user's live account (one-time probe)."""
from unittest.mock import MagicMock

import backend.db as db
import backend.garmin_client as gc


# --- db: new daily columns roundtrip ---

def test_daily_new_columns_roundtrip(tmp_path):
    p = tmp_path / "d.db"
    db.init_db(p)
    metrics = {f: None for f in db.DAILY_FIELDS}
    metrics.update({"recovery_time_min": 2079, "nap_time_s": 0,
                    "skin_temp_dev_c": -0.3, "spo2_avg": 94, "spo2_lowest": 89,
                    "spo2_avg_sleep": 94, "hydration_ml": 500,
                    "hydration_goal_ml": 4231, "sweat_loss_ml": 1392})
    db.upsert_daily(p, "2026-07-12", metrics, 50, 40)
    row = db.get_daily(p, "2026-07-12")
    assert row["recovery_time_min"] == 2079
    assert row["spo2_avg"] == 94
    assert row["sweat_loss_ml"] == 1392
    assert row["skin_temp_dev_c"] == -0.3


def test_perf_new_columns_roundtrip(tmp_path):
    p = tmp_path / "d.db"
    db.init_db(p)
    db.upsert_perf(p, "2026-07-12", {
        "vo2max": 54, "fitness_age": 18, "running_tolerance_load": 15540,
        "running_tolerance_ceiling": 35494, "hill_score": 28, "lt_hr": 180,
        "lt_power": 320, "body_weight_g": 57100})
    row = db.get_latest_perf(p)
    assert row["fitness_age"] == 18
    assert row["running_tolerance_ceiling"] == 35494
    assert row["hill_score"] == 28
    assert row["lt_hr"] == 180
    assert row["body_weight_g"] == 57100


def test_perf_upsert_merges_not_wipes(tmp_path):
    """A later sync where one endpoint failed (None) must not wipe a stored value."""
    p = tmp_path / "d.db"
    db.init_db(p)
    db.upsert_perf(p, "2026-07-12", {"vo2max": 54, "hill_score": 28})
    db.upsert_perf(p, "2026-07-12", {"vo2max": 54, "hill_score": None})
    assert db.get_latest_perf(p)["hill_score"] == 28


def test_activity_dynamics_roundtrip(tmp_path):
    p = tmp_path / "d.db"
    db.init_db(p)
    dyn = {"cadence": 169.3, "avg_power": 252, "ground_contact_time": 259.5}
    db.upsert_activity_detail(p, 42, dynamics_json=dyn)
    got = db.get_activity_detail(p, 42)
    assert got["dynamics"]["cadence"] == 169.3
    assert got["dynamics"]["avg_power"] == 252


# --- garmin_client: parsing the real payload shapes ---

def _client():
    c = gc.GarminClient("e", "p", "ts")
    c._api = MagicMock()
    return c


def test_fetch_day_parses_recovery_naps_skin_spo2_hydration():
    c = _client()
    api = c._api
    api.get_user_summary.return_value = {"restingHeartRate": 48}
    api.get_sleep_data.return_value = {
        "dailySleepDTO": {"napTimeSeconds": 0, "sleepScores": {}},
        "avgSkinTempDeviationC": -0.4}
    api.get_hrv_data.return_value = {"hrvSummary": {"lastNightAvg": 60}}
    api.get_training_readiness.return_value = [{"score": 50, "recoveryTime": 2079}]
    api.get_max_metrics.return_value = []
    api.get_intensity_minutes_data.return_value = {}
    api.get_respiration_data.return_value = {}
    api.get_training_status.return_value = {}
    api.get_spo2_data.return_value = {"averageSpO2": 94.0, "lowestSpO2": 89,
                                      "avgSleepSpO2": 94.0}
    api.get_hydration_data.return_value = {"valueInML": 500.0, "goalInML": 4231.0,
                                           "sweatLossInML": 1392.0}
    metrics, _ = c.fetch_day("2026-07-12")
    assert metrics["recovery_time_min"] == 2079
    assert metrics["nap_time_s"] == 0
    assert metrics["skin_temp_dev_c"] == -0.4
    assert metrics["spo2_avg"] == 94.0
    assert metrics["spo2_lowest"] == 89
    assert metrics["sweat_loss_ml"] == 1392.0


def test_fetch_baseline_includes_naps_and_skin_temp():
    c = _client()
    api = c._api
    api.get_user_summary.return_value = {"restingHeartRate": 48}
    api.get_hrv_data.return_value = {"hrvSummary": {"lastNightAvg": 60}}
    api.get_sleep_data.return_value = {
        "dailySleepDTO": {"napTimeSeconds": 1200, "sleepScores": {}},
        "avgSkinTempDeviationC": 0.2}
    base = c.fetch_baseline("2026-07-01")
    assert base["nap_time_s"] == 1200
    assert base["skin_temp_dev_c"] == 0.2


def test_fetch_performance_parses_all_new_metrics():
    c = _client()
    api = c._api
    api.get_training_status.return_value = {}
    api.get_max_metrics.return_value = []
    api.get_race_predictions.return_value = {}
    api.get_endurance_score.return_value = {}
    api.get_fitnessage_data.return_value = {"fitnessAge": 18.0, "chronologicalAge": 21}
    api.get_running_tolerance.return_value = [
        {"totalImpactLoad": 9000, "tolerance": 30000},
        {"totalImpactLoad": 15540, "tolerance": 35494}]
    api.get_hill_score.return_value = {"maxScore": 28, "periodAvgScore": {}}
    api.get_lactate_threshold.return_value = {
        "speed_and_heart_rate": {"heartRate": 180, "speed": 0.405},
        "power": {"functionalThresholdPower": 320}}
    api.get_body_composition.return_value = {"totalAverage": {"weight": 57100.0}}
    perf = c.fetch_performance("2026-07-12")
    assert perf["fitness_age"] == 18.0
    assert perf["running_tolerance_load"] == 15540   # latest week
    assert perf["running_tolerance_ceiling"] == 35494
    assert perf["hill_score"] == 28
    assert perf["lt_hr"] == 180
    assert perf["lt_power"] == 320
    assert perf["body_weight_g"] == 57100.0


def test_fetch_activity_detail_parses_running_dynamics():
    c = _client()
    api = c._api
    api.get_activity_details.return_value = {"geoPolylineDTO": {}}
    api.get_activity_splits.return_value = {}
    api.get_activity_hr_in_timezones.return_value = []
    api.get_activity_weather.return_value = None
    api.get_activity_exercise_sets.return_value = None
    api.get_activity.return_value = {"summaryDTO": {
        "averageRunCadence": 169.3, "maxRunCadence": 178.0, "strideLength": 106.5,
        "groundContactTime": 259.5, "verticalOscillation": 9.36,
        "verticalRatio": 8.81, "averagePower": 252.0, "normalizedPower": 256.0,
        "maxPower": 369.0, "elevationGain": 97.0}}
    d = c.fetch_activity_detail(42)
    dyn = d["dynamics"]
    assert dyn["cadence"] == 169.3
    assert dyn["ground_contact_time"] == 259.5
    assert dyn["avg_power"] == 252.0
    assert dyn["vertical_ratio"] == 8.81


def test_running_dynamics_none_when_absent():
    c = _client()
    api = c._api
    api.get_activity_details.return_value = {"geoPolylineDTO": {}}
    api.get_activity_splits.return_value = {}
    api.get_activity_hr_in_timezones.return_value = []
    api.get_activity_weather.return_value = None
    api.get_activity_exercise_sets.return_value = None
    api.get_activity.return_value = {"summaryDTO": {"duration": 1800}}
    d = c.fetch_activity_detail(42)
    assert d["dynamics"] is None

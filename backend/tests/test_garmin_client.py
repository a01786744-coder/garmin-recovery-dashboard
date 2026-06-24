from unittest.mock import MagicMock, patch
import backend.garmin_client as gc

def test_clean_login_dumps_tokens():
    with patch.object(gc, "Garmin") as MockGarmin:
        api = MockGarmin.return_value
        api.login.return_value = (None, None)          # no MFA needed
        client = gc.GarminClient("e@x.com", "secret", "/tmp/ts")
        client.login()
        MockGarmin.assert_called_once_with("e@x.com", "secret", return_on_mfa=True)
        api.login.assert_called_once_with("/tmp/ts")
        api.client.dump.assert_called_once_with("/tmp/ts")   # tokens persisted

def test_login_raises_mfa_required_with_state():
    with patch.object(gc, "Garmin") as MockGarmin:
        api = MockGarmin.return_value
        api.login.return_value = ("needs_mfa", {"state": 1})
        client = gc.GarminClient("e@x.com", "secret", "/tmp/ts")
        try:
            client.login()
            assert False, "should raise"
        except gc.GarminMFARequired as e:
            assert e.client_state == {"state": 1}

def test_complete_mfa_resumes_and_dumps():
    with patch.object(gc, "Garmin") as MockGarmin:
        api = MockGarmin.return_value
        client = gc.GarminClient("e@x.com", "secret", "/tmp/ts")
        client._api = api                               # simulate post-login state
        client.complete_mfa({"state": 1}, "123456")
        api.resume_login.assert_called_once_with({"state": 1}, "123456")
        api.client.dump.assert_called_once_with("/tmp/ts")

def test_login_wraps_auth_error_without_leaking_creds():
    with patch.object(gc, "Garmin") as MockGarmin:
        from garminconnect import GarminConnectAuthenticationError
        MockGarmin.return_value.login.side_effect = GarminConnectAuthenticationError("bad")
        client = gc.GarminClient("e@x.com", "secret", "/tmp/ts")
        try:
            client.login()
            assert False, "should raise"
        except gc.GarminAuthError as e:
            assert "secret" not in str(e)

def _client_with_api(api):
    c = gc.GarminClient("e", "p", "/tmp")
    c._api = api
    return c

def test_fetch_day_handles_none_and_empty():
    api = MagicMock()
    api.get_user_summary.return_value = {
        "totalSteps": 1119, "totalKilocalories": 2202.0,
        "restingHeartRate": 52, "averageStressLevel": 28,
        "bodyBatteryMostRecentValue": 60,
    }
    api.get_sleep_data.return_value = {
        "dailySleepDTO": {
            "deepSleepSeconds": 3600, "lightSleepSeconds": 7200,
            "remSleepSeconds": 5400, "awakeSleepSeconds": 600,
            "sleepScores": {"overall": {"value": 82}},
        }
    }
    api.get_hrv_data.return_value = None                       # no-data day → None
    api.get_training_readiness.return_value = []               # empty list
    api.get_max_metrics.return_value = None
    metrics, avail = _client_with_api(api).fetch_day("2026-06-19")
    assert metrics["steps"] == 1119
    assert metrics["sleep_score"] == 82
    assert metrics["rhr"] == 52
    assert metrics["hrv_last_night"] is None
    assert avail["hrv_last_night"] == "unavailable"
    assert avail["steps"] == "available"
    assert metrics["training_readiness_score"] is None
    assert avail["training_readiness_score"] == "unavailable"

def test_fetch_day_never_raises_on_exception():
    api = MagicMock()
    api.get_user_summary.side_effect = KeyError("boom")
    api.get_sleep_data.return_value = None
    api.get_hrv_data.return_value = None
    api.get_training_readiness.return_value = []
    api.get_max_metrics.return_value = None
    metrics, avail = _client_with_api(api).fetch_day("2026-06-19")
    assert metrics["steps"] is None
    assert avail["steps"] == "unavailable"

def test_fetch_activities_tolerates_nulls_and_missing_fields():
    api = MagicMock()
    api.get_activities_by_date.return_value = [
        {"activityId": 1, "startTimeLocal": "2026-06-19 07:00:00",
         "activityType": {"typeKey": "running"}, "duration": 1800,
         "averageHR": 150, "maxHR": 170, "activityTrainingLoad": 120,
         "aerobicTrainingEffect": 3.0, "anaerobicTrainingEffect": 0.5},
        {"activityId": 2},                 # almost-empty activity
        None,                              # null entry
    ]
    acts = _client_with_api(api).fetch_activities("2026-05-20", "2026-06-19")
    assert len(acts) == 3
    assert acts[0]["type"] == "running"
    assert acts[0]["avg_hr"] == 150
    assert acts[1]["activity_id"] == 2
    assert acts[1]["type"] is None        # missing field → None, no crash
    assert acts[2]["activity_id"] is None # null entry handled

def test_last_fetch_had_errors_tracks_exceptions():
    api = MagicMock()
    api.get_user_summary.return_value = {"restingHeartRate": 50}
    api.get_hrv_data.return_value = {"hrvSummary": {"lastNightAvg": 40, "status": "BALANCED"}}
    api.get_sleep_data.return_value = {"dailySleepDTO": {
        "deepSleepSeconds": 3600, "lightSleepSeconds": 7200, "remSleepSeconds": 5400,
        "awakeSleepSeconds": 600, "sleepScores": {"overall": {"value": 82}}}}
    c = _client_with_api(api)
    base = c.fetch_baseline("2026-06-19")
    assert base["hrv_last_night"] == 40 and base["rhr"] == 50
    assert base["sleep_score"] == 82 and base["deep_sleep_s"] == 3600   # sleep now backfilled
    assert c.last_fetch_had_errors is False

def test_last_fetch_had_errors_true_on_transport_error():
    api = MagicMock()
    api.get_user_summary.side_effect = ConnectionError("429")   # transport error
    api.get_hrv_data.return_value = None
    api.get_sleep_data.return_value = {}
    c = _client_with_api(api)
    base = c.fetch_baseline("2026-06-19")
    assert base["rhr"] is None and base["sleep_score"] is None
    assert c.last_fetch_had_errors is True                       # vs genuine empty


# --- v2 Task 2: parsing for expanded metrics ---

def test_primary_device_value_picks_primary():
    m = {"1": {"primaryTrainingDevice": False, "x": 1},
         "2": {"primaryTrainingDevice": True, "x": 2}}
    assert gc._primary_device_value(m)["x"] == 2
    assert gc._primary_device_value({}) == {}


def test_fetch_day_parses_training_and_readiness():
    api = MagicMock()
    api.get_user_summary.return_value = {
        "restingHeartRate": 39, "totalSteps": 1574, "totalKilocalories": 1337.0,
        "activeKilocalories": 5.0, "bmrKilocalories": 1332.0, "averageStressLevel": 20,
        "bodyBatteryMostRecentValue": 50, "highlyActiveSeconds": 229, "activeSeconds": 324,
        "sedentarySeconds": 30287, "moderateIntensityMinutes": 0, "vigorousIntensityMinutes": 2,
        "intensityMinutesGoal": 150, "floorsAscended": 3.16, "totalDistanceMeters": 1228}
    api.get_sleep_data.return_value = {"dailySleepDTO": {
        "deepSleepSeconds": 5580, "lightSleepSeconds": 14160, "remSleepSeconds": 6960,
        "awakeSleepSeconds": 900, "awakeCount": 1, "avgOvernightHrv": 79,
        "sleepNeed": {"actual": 28800, "baseline": 27000},
        "sleepScores": {"overall": {"value": 91}, "deep": {"value": 80},
                        "rem": {"value": 70}, "light": {"value": 60},
                        "restlessness": {"value": 90}}}}
    api.get_hrv_data.return_value = {"hrvSummary": {"lastNightAvg": 79, "status": "BALANCED"}}
    api.get_intensity_minutes_data.return_value = {"weeklyTotal": 116, "weekGoal": 150}
    api.get_respiration_data.return_value = {"avgWakingRespirationValue": 12, "avgSleepRespirationValue": 13}
    api.get_training_readiness.return_value = [{"score": 75, "sleepScoreFactorPercent": 74,
        "recoveryTimeFactorPercent": 80, "acwrFactorPercent": 99, "hrvFactorPercent": 0,
        "stressHistoryFactorPercent": 98, "acuteLoad": 177}]
    api.get_training_status.return_value = {
        "mostRecentTrainingStatus": {"latestTrainingStatusData": {"3626478156": {
            "trainingStatusFeedbackPhrase": "PRODUCTIVE_1", "primaryTrainingDevice": True,
            "acuteTrainingLoadDTO": {"dailyAcuteChronicWorkloadRatio": 0.8,
                "dailyTrainingLoadAcute": 177, "dailyTrainingLoadChronic": 219}}}},
        "mostRecentTrainingLoadBalance": {"metricsTrainingLoadBalanceDTOMap": {"3626478156": {
            "monthlyLoadAerobicLow": 0.0, "monthlyLoadAerobicHigh": 150.7,
            "monthlyLoadAnaerobic": 0.0, "primaryTrainingDevice": True}}}}
    api.get_max_metrics.return_value = []
    metrics, avail = _client_with_api(api).fetch_day("2026-06-21")
    assert metrics["acwr_ratio"] == 0.8
    assert metrics["acute_load"] == 177
    assert metrics["training_status_label"] == "PRODUCTIVE_1"
    assert metrics["load_aerobic_high"] == 150.7
    assert metrics["tr_sleep_factor"] == 74
    assert metrics["sleep_deep_score"] == 80
    assert metrics["sleep_need_actual"] == 28800
    assert metrics["resp_sleep"] == 13
    assert metrics["intensity_weekly_total"] == 116
    assert metrics["sedentary_s"] == 30287
    assert metrics["sleep_score"] == 91


def test_fetch_performance_parses_predictions_and_endurance():
    api = MagicMock()
    api.get_training_status.return_value = {"mostRecentVO2Max": {"generic": {"vo2MaxValue": 60.0}}}
    api.get_max_metrics.return_value = []
    api.get_race_predictions.return_value = {"time5K": 1205, "time10K": 2536,
        "timeHalfMarathon": 5509, "timeMarathon": 12772}
    api.get_endurance_score.return_value = {"overallScore": 6892, "classification": 4}
    perf = _client_with_api(api).fetch_performance("2026-06-21")
    assert perf["vo2max"] == 60.0
    assert perf["race_5k"] == 1205 and perf["race_marathon"] == 12772
    assert perf["endurance_score"] == 6892 and perf["endurance_class"] == 4


def test_fetch_intraday_parses_arrays():
    api = MagicMock()
    api.get_heart_rates.return_value = {"heartRateValues": [[1, 48], [2, 50]]}
    api.get_stress_data.return_value = {"stressValuesArray": [[1, 20], [2, 25]]}
    api.get_body_battery.return_value = [{"bodyBatteryValuesArray": [[1, 38], [2, 40]]}]
    api.get_hrv_data.return_value = {"hrvReadings": [{"hrvValue": 63, "readingTimeGMT": "t"}]}
    intr = _client_with_api(api).fetch_intraday("2026-06-21")
    assert intr["hr"] == [[1, 48], [2, 50]]
    assert intr["body_battery"] == [[1, 38], [2, 40]]
    assert intr["hrv"][0]["hrvValue"] == 63


def test_fetch_activity_detail_parses_polyline_and_zones():
    api = MagicMock()
    api.get_activity_details.return_value = {"geoPolylineDTO": {
        "polyline": [{"lat": 30.1, "lon": -95.5}], "minLat": 30.0, "maxLat": 30.2}}
    api.get_activity_splits.return_value = {"lapDTOs": [{"distance": 1000, "averageHR": 150}]}
    api.get_activity_hr_in_timezones.return_value = [{"zoneNumber": 1, "secsInZone": 193}]
    api.get_activity_weather.return_value = {"temp": 20}
    d = _client_with_api(api).fetch_activity_detail(999)
    assert d["polyline"][0]["lat"] == 30.1
    assert d["splits"][0]["averageHR"] == 150
    assert d["hr_zones"][0]["zoneNumber"] == 1
    assert d["summary"]["minLat"] == 30.0

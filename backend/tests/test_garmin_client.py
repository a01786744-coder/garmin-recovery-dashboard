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

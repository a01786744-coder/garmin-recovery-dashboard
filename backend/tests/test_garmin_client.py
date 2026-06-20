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

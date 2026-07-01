import backend.settings as st


def test_phone_access_and_pin_defaults(tmp_path):
    s = st.load_settings(tmp_path / "settings.json")
    assert s["phone_access"] is False
    assert s["access_pin"] == ""


def test_phone_access_coerced_to_bool_and_pin_to_str(tmp_path):
    p = tmp_path / "settings.json"
    saved = st.save_settings(p, {"phone_access": 1, "access_pin": 1234})
    assert saved["phone_access"] is True
    assert saved["access_pin"] == "1234"
    assert st.load_settings(p) == saved

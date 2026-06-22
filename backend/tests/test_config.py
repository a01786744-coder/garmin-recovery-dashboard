import backend.config as cfg


def test_resolve_data_dir_uses_env_override(tmp_path):
    target = tmp_path / "userdata"
    got = cfg.resolve_data_dir({"GARMIN_DASH_DATA_DIR": str(target)}, project_root="/proj")
    assert str(got) == str(target)


def test_resolve_data_dir_falls_back_to_project_data():
    got = cfg.resolve_data_dir({}, project_root="/proj")
    # falls back to <project_root>/data when no override is set
    assert got.name == "data"
    assert str(got).replace("\\", "/").endswith("proj/data")


def test_per_user_paths_live_under_data_dir():
    # DB, token store, capability profile, settings, and log all resolve under DATA_DIR
    for p in (cfg.DB_PATH, cfg.TOKENSTORE_DIR, cfg.CAPABILITY_PATH, cfg.SETTINGS_PATH, cfg.LOG_PATH):
        assert str(p).startswith(str(cfg.DATA_DIR))

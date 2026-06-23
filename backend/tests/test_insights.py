import backend.insights as ins

def _day(date, **kw):
    base = {"date": date, "recovery_score": None, "sleep_score": None,
            "strain_score": None, "hrv_last_night": None, "rhr": None,
            "deep_sleep_s": None, "light_sleep_s": None, "rem_sleep_s": None}
    base.update(kw); return base

def test_weekly_recap_deltas():
    daily = [_day(f"2026-05-{d:02d}", recovery_score=50) for d in range(1, 8)]
    daily += [_day(f"2026-05-{d:02d}", recovery_score=60) for d in range(8, 15)]
    wk = ins.weekly_recap(daily, [])
    assert wk["recovery_score"]["this"] == 60
    assert wk["recovery_score"]["last"] == 50
    assert wk["recovery_score"]["delta"] == 10

def test_weekly_recap_null_side_gives_none_delta():
    daily = [_day(f"2026-05-{d:02d}", recovery_score=60) for d in range(8, 15)]  # only this week
    wk = ins.weekly_recap(daily, [])
    assert wk["recovery_score"]["this"] == 60
    assert wk["recovery_score"]["last"] is None
    assert wk["recovery_score"]["delta"] is None

def test_streaks_green_recovery_and_break():
    daily = [_day("2026-06-18", recovery_score=70), _day("2026-06-19", recovery_score=40),
             _day("2026-06-20", recovery_score=80), _day("2026-06-21", recovery_score=72)]
    s = ins.streaks(daily, [])
    assert s["green_recovery"] == 2          # last two days >= 67, the 40 breaks it

def test_streaks_workout():
    daily = [_day("2026-06-20"), _day("2026-06-21")]
    acts = [{"date": "2026-06-21"}]
    assert ins.streaks(daily, acts)["workout"] == 1

def test_auto_insights_hrv_trend_up():
    daily = [_day(f"2026-06-{d:02d}", hrv_last_night=40) for d in range(8, 15)]
    daily += [_day(f"2026-06-{d:02d}", hrv_last_night=48) for d in range(15, 22)]
    out = ins.auto_insights(daily)
    assert any(i["metric"] == "hrv" and "up" in i["text"].lower() for i in out)

def test_auto_insights_thin_data_empty():
    assert ins.auto_insights([_day("2026-06-21", hrv_last_night=40)]) == []

def test_correlations_thin_data_empty():
    assert ins.correlations([_day("2026-06-21", recovery_score=60)]) == []

def test_correlations_sleep_to_recovery():
    # 12 days of varied sleep durations; each night's sleep predicts the NEXT
    # day's recovery (correlation pairs are sleep[i] -> recovery[i+1]). Varied
    # (non-bimodal) durations so the median split has a populated high group.
    hours = [6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 6.2, 6.8, 7.2, 7.8, 8.2, 8.6]
    daily = []
    for i, h in enumerate(hours):
        total = int(h * 3600)
        daily.append(_day(f"2026-06-{i+1:02d}",
                          deep_sleep_s=int(total * 0.2),
                          light_sleep_s=int(total * 0.6),
                          rem_sleep_s=int(total * 0.2)))
    for i in range(1, len(daily)):
        daily[i]["recovery_score"] = 40 + (hours[i - 1] - 6) * 10  # more prior sleep -> higher recovery
    out = ins.correlations(daily)
    assert any("sleep" in c["text"].lower() for c in out)

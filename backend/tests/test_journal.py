"""Journal: daily tags with sticky prefill from the previous entry, plus
tag→next-day-recovery correlations. Local-only, no fabrication."""
from unittest.mock import MagicMock

import backend.db as db
from backend.api import create_app
from backend.insights import journal_correlations, JOURNAL_TAGS


def _client(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    app = create_app(p, client_factory=lambda: MagicMock(),
                     tokenstore=tmp_path / "garth")
    return app.test_client(), p


# --- db layer ---

def test_journal_roundtrip(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    db.upsert_journal(p, "2026-07-01", {"alcohol": True, "nap": False}, "long day")
    e = db.get_journal(p, "2026-07-01")
    assert e["tags"]["alcohol"] is True
    assert e["note"] == "long day"
    assert db.get_journal(p, "2026-06-30") is None


def test_journal_latest_before(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    db.upsert_journal(p, "2026-06-28", {"alcohol": True}, "")
    db.upsert_journal(p, "2026-07-01", {"alcohol": False, "sick": True}, "")
    prev = db.get_journal_before(p, "2026-07-02")
    assert prev["date"] == "2026-07-01"
    assert db.get_journal_before(p, "2026-06-28") is None


# --- API: sticky prefill ---

def test_get_journal_prefills_from_previous_entry(tmp_path):
    client, p = _client(tmp_path)
    db.upsert_journal(p, "2026-07-01", {"alcohol": True, "high_stress": True}, "x")
    body = client.get("/api/journal/2026-07-02").get_json()
    assert body["saved"] is False                       # nothing saved for the 2nd
    assert body["tags"]["alcohol"] is True              # carried forward
    assert body["tags"]["high_stress"] is True
    assert body["note"] == ""                           # notes never carry forward


def test_get_journal_returns_saved_entry_as_saved(tmp_path):
    client, p = _client(tmp_path)
    db.upsert_journal(p, "2026-07-02", {"alcohol": False}, "quiet")
    body = client.get("/api/journal/2026-07-02").get_json()
    assert body["saved"] is True and body["note"] == "quiet"


def test_post_journal_saves_and_filters_unknown_tags(tmp_path):
    client, p = _client(tmp_path)
    r = client.post("/api/journal/2026-07-02",
                    json={"tags": {"alcohol": True, "bogus_tag": True}, "note": "n"})
    body = r.get_json()
    assert body["saved"] is True
    assert body["tags"]["alcohol"] is True
    assert "bogus_tag" not in body["tags"]


def test_journal_rejects_malformed_date(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/api/journal/not-a-date").status_code == 400


# --- correlations: tag vs next-day recovery ---

def _daily(n=16, base=60):
    """Days 07-01..07-16 with recovery scores; even days low, odd days high."""
    out = []
    for i in range(1, n + 1):
        out.append({"date": f"2026-07-{i:02d}",
                    "recovery_score": base - 15 if i % 2 == 0 else base + 15})
    return out


def test_journal_correlation_reports_tag_effect():
    daily = _daily()
    # Tag alcohol on days whose NEXT day is even (low recovery) -> negative delta
    entries = [{"date": f"2026-07-{i:02d}", "tags": {"alcohol": (i % 2 == 1)}}
               for i in range(1, 16)]
    out = journal_correlations(daily, entries)
    assert any("alcohol" in c["text"].lower() and "lower" in c["text"] for c in out)


def test_journal_correlation_silent_on_thin_data():
    assert journal_correlations(_daily(4), [{"date": "2026-07-01", "tags": {"alcohol": True}}]) == []
    assert journal_correlations([], []) == []


def test_journal_tags_is_a_fixed_known_set():
    assert "alcohol" in JOURNAL_TAGS and "screens_in_bed" in JOURNAL_TAGS
    assert len(JOURNAL_TAGS) == 8

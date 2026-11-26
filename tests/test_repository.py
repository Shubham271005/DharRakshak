"""
Unit tests for the data-access layer (backend/repository.py).

The repository is the only module that touches SQL, so this is where the
storage contract is pinned: every read returns a validated contract model,
derived values are always fresh, and the Phase 1 robustness fixes stay fixed
(UTC-normalised timestamps, atomic seed, tolerance of a corrupt row).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from backend import repository
from backend.db import connect, init_db
from backend.engines.content import load
from backend.sample_store import sample
from shared.contract import CropProfileCreate, CropStage, RiskLevel


@pytest.fixture
def seeded(db_file):
    init_db()
    repository.seed_demo_if_empty()
    return db_file


def new_crop(**kwargs) -> CropProfileCreate:
    payload = dict(
        farmer_name="Sunita Devi", crop_type="wheat", variety="HD-2967",
        sowing_date=date.today() - timedelta(days=40), area_acres=2.5,
        location_name="Karnal, Haryana", stage=CropStage.vegetative,
    )
    payload.update(kwargs)
    return CropProfileCreate(**payload)


# ---------------------------------------------------------------------------
# Crops
# ---------------------------------------------------------------------------


def test_a_created_crop_reads_back_identically(seeded):
    created = repository.create_crop(new_crop(), 29.69, 76.98)
    fetched = repository.get_crop(created.crop_id)
    assert fetched is not None
    assert fetched.crop_id == created.crop_id
    assert fetched.crop_type == "wheat"
    assert fetched.variety == "HD-2967"
    assert fetched.location.latitude == 29.69
    assert fetched.stage is CropStage.vegetative


def test_an_unknown_crop_returns_none(seeded):
    assert repository.get_crop("crop-does-not-exist") is None


def test_days_since_sowing_is_computed_on_every_read(seeded):
    created = repository.create_crop(new_crop(sowing_date=date.today() - timedelta(days=10)), 1.0, 1.0)
    assert repository.get_crop(created.crop_id).days_since_sowing == 10
    # Rewriting the row's sowing date changes the computed value, because it is
    # never stored.
    with connect() as conn:
        conn.execute("UPDATE crops SET sowing_date = ? WHERE crop_id = ?",
                     ((date.today() - timedelta(days=25)).isoformat(), created.crop_id))
    assert repository.get_crop(created.crop_id).days_since_sowing == 25


def test_a_future_sowing_date_never_produces_negative_days(seeded):
    created = repository.create_crop(new_crop(), 1.0, 1.0)
    with connect() as conn:                      # bypass the form validation
        conn.execute("UPDATE crops SET sowing_date = ? WHERE crop_id = ?",
                     ((date.today() + timedelta(days=5)).isoformat(), created.crop_id))
    assert repository.get_crop(created.crop_id).days_since_sowing == 0


def test_a_blank_variety_is_stored_as_null(seeded):
    created = repository.create_crop(new_crop(variety=""), 1.0, 1.0)
    assert repository.get_crop(created.crop_id).variety is None


def test_creating_a_crop_for_an_existing_farmer_keeps_one_farmer(seeded):
    demo = repository.get_crop(sample().crop_profile.crop_id)
    second = repository.create_crop(
        new_crop(farmer_id=demo.farmer_id, farmer_name="Renamed Farmer"), 1.0, 1.0)
    assert second.farmer_id == demo.farmer_id
    assert repository.get_crop(second.crop_id).farmer_name == "Renamed Farmer"
    # The first crop's read still joins the same (updated) farmer row.
    assert repository.get_crop(demo.crop_id).farmer_name == "Renamed Farmer"


def test_creating_a_crop_for_an_unknown_farmer_raises(seeded):
    with pytest.raises(repository.UnknownFarmer):
        repository.create_crop(new_crop(farmer_id="farmer-nope"), 1.0, 1.0)


def test_a_failed_crop_insert_leaves_nothing_behind(seeded):
    before = len(repository.list_crops())
    with pytest.raises(repository.UnknownFarmer):
        repository.create_crop(new_crop(farmer_id="farmer-nope"), 1.0, 1.0)
    assert len(repository.list_crops()) == before


def test_crops_are_listed_newest_first(seeded):
    older = repository.create_crop(new_crop(farmer_name="Older"), 1.0, 1.0)
    newer = repository.create_crop(new_crop(farmer_name="Newer"), 1.0, 1.0)
    ids = [item.profile.crop_id for item in repository.list_crops()]
    assert ids.index(newer.crop_id) < ids.index(older.crop_id)


def test_a_crop_with_no_checks_has_an_empty_summary(seeded):
    created = repository.create_crop(new_crop(), 1.0, 1.0)
    item = next(i for i in repository.list_crops() if i.profile.crop_id == created.crop_id)
    assert item.checks == 0
    assert item.latest_check_at is None
    assert item.latest_risk is None
    assert item.latest_prediction is None


def test_the_check_summary_reports_the_newest_analysis(seeded):
    stored = sample().analysis
    item = next(i for i in repository.list_crops() if i.profile.crop_id == stored.crop_id)
    assert item.checks == 1
    assert item.latest_risk is stored.risk.level
    assert item.latest_prediction == stored.predictions[0].display_name
    assert item.latest_check_at is not None


def test_update_replaces_every_editable_field_but_keeps_the_id(seeded):
    created = repository.create_crop(new_crop(), 1.0, 1.0)
    updated = repository.update_crop(created.crop_id, new_crop(
        farmer_name="New Name", crop_type="mustard", variety=None,
        area_acres=9.0, location_name="Hisar", stage=CropStage.flowering), 29.15, 75.72)
    assert updated.crop_id == created.crop_id
    assert updated.crop_type == "mustard"
    assert updated.variety is None
    assert updated.area_acres == 9.0
    assert updated.location.name == "Hisar"
    assert updated.stage is CropStage.flowering
    assert updated.farmer_name == "New Name"


def test_updating_an_unknown_crop_returns_none(seeded):
    assert repository.update_crop("crop-nope", new_crop(), 1.0, 1.0) is None


def test_update_keeps_the_sowing_date_history_of_analyses(seeded):
    stored = sample().analysis
    repository.update_crop(stored.crop_id, new_crop(
        sowing_date=date.today() - timedelta(days=5), stage=CropStage.seedling), 1.0, 1.0)
    assert len(repository.list_analyses(stored.crop_id)) == 1


# ---------------------------------------------------------------------------
# Analyses
# ---------------------------------------------------------------------------


def analysis_with(**kwargs):
    base = sample().analysis.model_copy(deep=True)
    return base.model_copy(update=kwargs) if kwargs else base


def test_a_saved_analysis_round_trips(seeded):
    result = analysis_with(analysis_id="an-test-0001")
    repository.save_analysis(result)
    stored = repository.list_analyses(result.crop_id, limit=5)
    assert any(a.analysis_id == "an-test-0001" for a in stored)
    fetched = next(a for a in stored if a.analysis_id == "an-test-0001")
    assert fetched.predictions == result.predictions
    assert fetched.risk.level == result.risk.level
    assert fetched.explanation.summary == result.explanation.summary


def test_analyses_are_returned_newest_first(seeded):
    base = sample().analysis
    older = analysis_with(analysis_id="an-older",
                          created_at=datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc))
    newer = analysis_with(analysis_id="an-newer",
                          created_at=datetime(2026, 1, 2, 6, 0, tzinfo=timezone.utc))
    repository.save_analysis(older)
    repository.save_analysis(newer)
    ids = [a.analysis_id for a in repository.list_analyses(base.crop_id)]
    assert ids.index("an-newer") < ids.index("an-older")


def test_timestamps_are_stored_in_utc_so_text_order_matches_time_order(seeded):
    """Phase 1 finding #6: mixed offsets made the newest row sort as older."""
    base = sample().analysis
    ist = timezone(timedelta(hours=5, minutes=30))
    # 11:00 IST is LATER than 10:30 IST, but as text "…T05:30+00:00" < "…T10:30+05:30".
    earlier = analysis_with(analysis_id="an-ist-1030",
                            created_at=datetime(2026, 3, 1, 10, 30, tzinfo=ist))
    later = analysis_with(analysis_id="an-utc-0600",
                          created_at=datetime(2026, 3, 1, 6, 0, tzinfo=timezone.utc))
    repository.save_analysis(earlier)
    repository.save_analysis(later)
    ids = [a.analysis_id for a in repository.list_analyses(base.crop_id)]
    assert ids.index("an-utc-0600") < ids.index("an-ist-1030")

    with connect() as conn:
        raw = conn.execute("SELECT created_at FROM analyses WHERE analysis_id = ?",
                           ("an-ist-1030",)).fetchone()[0]
    assert raw.endswith("+00:00")


def test_a_naive_timestamp_is_read_as_utc(seeded):
    base = sample().analysis
    repository.save_analysis(analysis_with(analysis_id="an-naive",
                                           created_at=datetime(2026, 4, 1, 12, 0)))
    assert any(a.analysis_id == "an-naive" for a in repository.list_analyses(base.crop_id))


def test_the_limit_caps_how_many_analyses_come_back(seeded):
    base = sample().analysis
    for i in range(5):
        repository.save_analysis(analysis_with(
            analysis_id=f"an-many-{i}",
            created_at=datetime(2026, 5, 1 + i, 6, 0, tzinfo=timezone.utc)))
    assert len(repository.list_analyses(base.crop_id, limit=2)) == 2


def test_an_unknown_crop_has_no_analyses(seeded):
    assert repository.list_analyses("crop-nope") == []


def test_a_corrupt_saved_analysis_is_skipped_not_fatal(seeded):
    """Phase 1 finding #7: one bad row must not break the whole screen."""
    base = sample().analysis
    good = analysis_with(analysis_id="an-good",
                         created_at=datetime(2026, 6, 1, 6, 0, tzinfo=timezone.utc))
    repository.save_analysis(good)
    with connect() as conn:
        conn.execute("INSERT INTO analyses VALUES (?, ?, ?, ?, ?, ?, ?)",
                     ("an-corrupt", base.crop_id, "2026-06-02T06:00:00+00:00",
                      "x", "low", 0, "{not json"))
    stored = repository.list_analyses(base.crop_id)
    ids = [a.analysis_id for a in stored]
    assert "an-good" in ids
    assert "an-corrupt" not in ids

    # And the crop list still renders, without a summary from the bad row.
    items = repository.list_crops()
    assert any(i.profile.crop_id == base.crop_id for i in items)


def test_the_contract_rejects_an_impossible_analysis(seeded):
    """Anything stored must satisfy the contract, so a bad value cannot be
    written through the normal path."""
    from shared.contract import AnalysisResult, Risk

    base = sample().analysis
    with pytest.raises(ValueError):
        Risk.model_validate({**base.risk.model_dump(), "score": -1})
    with pytest.raises(ValueError):
        # Predictions out of order are rejected by the model validator.
        AnalysisResult.model_validate({
            **base.model_dump(),
            "predictions": list(reversed([p.model_dump() for p in base.predictions])),
        })


# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------


def test_the_seeded_loan_summary_is_internally_consistent(seeded):
    summary = repository.get_loan_summary(sample().crop_profile.crop_id)
    assert summary is not None
    assert summary.data_source == "mock"
    expected = sorted(d.code for d in summary.documents if not d.submitted)
    assert sorted(summary.missing_document_codes) == expected


def test_a_farmer_without_a_loan_gets_none(seeded):
    created = repository.create_crop(new_crop(), 1.0, 1.0)   # a brand-new farmer
    assert repository.get_loan_summary(created.crop_id) is None


def test_a_document_can_be_ticked_and_unticked(seeded):
    crop_id = sample().crop_profile.crop_id
    before = repository.get_loan_summary(crop_id)
    code = before.documents[0].code

    ticked = repository.set_document_submitted(crop_id, code, True)
    assert next(d for d in ticked.documents if d.code == code).submitted is True
    assert code not in ticked.missing_document_codes

    unticked = repository.set_document_submitted(crop_id, code, False)
    assert next(d for d in unticked.documents if d.code == code).submitted is False
    assert code in unticked.missing_document_codes


def test_ticking_a_known_document_does_not_touch_the_others(seeded):
    crop_id = sample().crop_profile.crop_id
    before = {d.code: d.submitted for d in repository.get_loan_summary(crop_id).documents}
    code = next(iter(before))
    after = {d.code: d.submitted for d in repository.set_document_submitted(crop_id, code, True).documents}
    for other, submitted in before.items():
        if other != code:
            assert after[other] is submitted


def test_an_unknown_document_code_returns_none(seeded):
    assert repository.set_document_submitted(sample().crop_profile.crop_id, "no_such_doc", True) is None


def test_ticking_a_document_for_a_farmer_without_a_loan_returns_none(seeded):
    created = repository.create_crop(new_crop(), 1.0, 1.0)
    assert repository.set_document_submitted(created.crop_id, "land_record", True) is None


def test_schemes_follow_the_loan_type(seeded):
    summary = repository.get_loan_summary(sample().crop_profile.crop_id)
    expected_codes = load("schemes")["by_loan_type"].get(summary.loan.loan_type, [])
    assert [s.code for s in summary.schemes] == expected_codes


def test_an_unknown_loan_type_has_no_schemes():
    assert repository.schemes_for("no_such_loan") == []


def test_every_scheme_used_by_a_loan_type_exists():
    content = load("schemes")
    for loan_type, codes in content["by_loan_type"].items():
        for code in codes:
            assert code in content["schemes"], f"{loan_type} → {code}"


# ---------------------------------------------------------------------------
# Demo seed
# ---------------------------------------------------------------------------


def test_the_seed_creates_exactly_one_of_everything(db_file):
    init_db()
    assert repository.seed_demo_if_empty() is True
    assert len(repository.list_crops()) == 1
    crop = repository.list_crops()[0].profile
    assert len(repository.list_analyses(crop.crop_id)) == 1
    assert repository.get_loan_summary(crop.crop_id) is not None


def test_the_seed_is_idempotent(seeded):
    assert repository.seed_demo_if_empty() is False
    assert len(repository.list_crops()) == 1


def test_a_concurrent_seed_does_not_raise(seeded):
    """Phase 1 finding #3: the check-then-act race killed a worker on startup."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: repository.seed_demo_if_empty(), range(8)))
    assert results.count(True) == 0         # already seeded, so nobody inserted
    assert len(repository.list_crops()) == 1


def test_the_seed_refuses_to_run_over_a_real_crop(db_file):
    init_db()
    repository.create_crop(new_crop(), 1.0, 1.0)
    assert repository.seed_demo_if_empty() is False
    assert len(repository.list_crops()) == 1
    assert all(i.profile.crop_id != sample().crop_profile.crop_id
               for i in repository.list_crops())


def test_the_seeded_analysis_is_the_sample_and_is_marked_demo(seeded):
    stored = repository.list_analyses(sample().crop_profile.crop_id, limit=1)
    assert len(stored) == 1
    assert stored[0].analysis_id == sample().analysis.analysis_id
    assert stored[0].is_demo is True


def test_the_seed_uses_the_localised_checklist_from_content(seeded):
    summary = repository.get_loan_summary(sample().crop_profile.crop_id)
    checklist = load("loan_documents")[summary.loan.loan_type]
    assert [d.code for d in summary.documents] == [d["code"] for d in checklist]
    for document in summary.documents:
        assert document.name.en.strip() and document.name.hi.strip()


def test_the_seeded_language_survives_a_round_trip(seeded):
    crop = repository.get_crop(sample().crop_profile.crop_id)
    assert crop.preferred_language == sample().crop_profile.preferred_language


# ---------------------------------------------------------------------------
# Schema guarantees
# ---------------------------------------------------------------------------


def test_foreign_keys_are_enforced_on_every_connection(seeded):
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        with connect() as conn:
            conn.execute(
                "INSERT INTO crops (crop_id, farmer_id, crop_type, sowing_date, area_acres,"
                " location_name, latitude, longitude, stage) VALUES (?,?,?,?,?,?,?,?,?)",
                ("crop-orphan", "farmer-nope", "wheat", "2026-01-01", 1, "x", 1, 1, "vegetative"))


def test_deleting_a_farmer_removes_their_crops_and_analyses(seeded):
    crop_id = sample().crop_profile.crop_id
    with connect() as conn:
        conn.execute("DELETE FROM farmers WHERE farmer_id = ?", (repository.DEMO_FARMER_ID,))
        assert conn.execute("SELECT 1 FROM crops WHERE crop_id = ?", (crop_id,)).fetchone() is None
        assert conn.execute("SELECT 1 FROM analyses WHERE crop_id = ?", (crop_id,)).fetchone() is None
        assert conn.execute("SELECT 1 FROM loans WHERE farmer_id = ?",
                            (repository.DEMO_FARMER_ID,)).fetchone() is None
        assert conn.execute("SELECT 1 FROM loan_documents").fetchone() is None


def test_the_database_runs_in_wal_mode(seeded):
    with connect() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_risk_levels_stored_are_readable_as_the_enum(seeded):
    stored = repository.list_analyses(sample().crop_profile.crop_id)[0]
    assert isinstance(stored.risk.level, RiskLevel)

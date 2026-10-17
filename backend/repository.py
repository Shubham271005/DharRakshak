"""
Data access layer (Component 3).

The ONLY module that reads or writes the database. Every function takes
or returns models from shared/contract.py, so the rest of the backend
never deals with SQL rows.

Coordinates are resolved by the caller (backend/main.py: GPS from the form,
or Open-Meteo geocoding) and passed in — this module only stores data.

Loan schemes come from shared/content/schemes.json (by loan type).
"""

from __future__ import annotations

import json
import uuid
from datetime import date

from backend.db import connect
from backend.engines.content import load
from backend.sample_store import sample
from shared.contract import (
    AnalysisResult,
    CropListItem,
    CropProfile,
    CropProfileCreate,
    DocumentItem,
    Loan,
    LoanSummary,
    Scheme,
    LocalizedText,
    Location,
    RepaymentDue,
    YieldRange,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# F2 — crops
# ---------------------------------------------------------------------------

_CROP_SELECT = """
    SELECT c.*, f.name AS farmer_name, f.preferred_language
    FROM crops c JOIN farmers f ON f.farmer_id = c.farmer_id
"""


def _row_to_crop(row) -> CropProfile:
    """Convert a crops+farmers row into the contract model.

    `days_since_sowing` is computed on every read, so it's always current.
    """
    sowing = date.fromisoformat(row["sowing_date"])
    yield_estimate = None
    if row["yield_min_kg"] is not None and row["yield_max_kg"] is not None:
        yield_estimate = YieldRange(min_kg=row["yield_min_kg"], max_kg=row["yield_max_kg"])
    return CropProfile(
        crop_id=row["crop_id"],
        farmer_id=row["farmer_id"],
        farmer_name=row["farmer_name"],
        preferred_language=row["preferred_language"],
        crop_type=row["crop_type"],
        variety=row["variety"],
        sowing_date=sowing,
        days_since_sowing=max(0, (date.today() - sowing).days),
        area_acres=row["area_acres"],
        location=Location(name=row["location_name"], latitude=row["latitude"], longitude=row["longitude"]),
        stage=row["stage"],
        expected_harvest_start=row["expected_harvest_start"],
        expected_harvest_end=row["expected_harvest_end"],
        yield_estimate=yield_estimate,
    )


def get_crop(crop_id: str) -> CropProfile | None:
    with connect() as conn:
        row = conn.execute(f"{_CROP_SELECT} WHERE c.crop_id = ?", (crop_id,)).fetchone()
    return _row_to_crop(row) if row else None


class UnknownFarmer(LookupError):
    """CropProfileCreate.farmer_id doesn't exist. The API returns 404."""


def create_crop(new: CropProfileCreate, lat: float, lon: float) -> CropProfile:
    """Add a crop. With `new.farmer_id` it belongs to that existing farmer
    (their name/language are updated from the form); without it a new
    farmer is created."""
    crop_id = _new_id("crop")
    with connect() as conn:
        if new.farmer_id:
            farmer_id = new.farmer_id
            updated = conn.execute(
                "UPDATE farmers SET name = ?, preferred_language = ? WHERE farmer_id = ?",
                (new.farmer_name, new.preferred_language, farmer_id),
            ).rowcount
            if not updated:
                raise UnknownFarmer(farmer_id)
        else:
            farmer_id = _new_id("farmer")
            conn.execute(
                "INSERT INTO farmers (farmer_id, name, preferred_language) VALUES (?, ?, ?)",
                (farmer_id, new.farmer_name, new.preferred_language),
            )
        conn.execute(
            """INSERT INTO crops (crop_id, farmer_id, crop_type, variety, sowing_date,
                                  area_acres, location_name, latitude, longitude, stage)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (crop_id, farmer_id, new.crop_type, new.variety or None, new.sowing_date.isoformat(),
             new.area_acres, new.location_name, lat, lon, new.stage.value),
        )
    return get_crop(crop_id)  # type: ignore[return-value]


def list_crops() -> list[CropListItem]:
    """Every crop on this device, newest first, with a summary of its checks.

    The app has no login yet (one device = one household), so "my crops" is
    every crop in the database. With accounts, filter by farmer_id here.
    """
    with connect() as conn:
        rows = conn.execute(f"{_CROP_SELECT} ORDER BY c.created_at DESC, c.rowid DESC").fetchall()
        stats = {
            r["crop_id"]: r
            for r in conn.execute(
                """SELECT a.crop_id, COUNT(*) AS checks, MAX(a.created_at) AS latest,
                          (SELECT result_json FROM analyses b WHERE b.crop_id = a.crop_id
                           ORDER BY b.created_at DESC LIMIT 1) AS latest_json
                   FROM analyses a GROUP BY a.crop_id"""
            ).fetchall()
        }
    items = []
    for row in rows:
        item = CropListItem(profile=_row_to_crop(row))
        s = stats.get(row["crop_id"])
        if s:
            latest = AnalysisResult.model_validate_json(s["latest_json"])
            item = item.model_copy(update={
                "checks": s["checks"],
                "latest_check_at": latest.created_at,
                "latest_risk": latest.risk.level,
                "latest_prediction": latest.predictions[0].display_name,
            })
        items.append(item)
    return items


def update_crop(crop_id: str, changes: CropProfileCreate, lat: float, lon: float) -> CropProfile | None:
    """Edit an existing crop (and its farmer's name/language). None if not found."""
    with connect() as conn:
        row = conn.execute("SELECT farmer_id FROM crops WHERE crop_id = ?", (crop_id,)).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE farmers SET name = ?, preferred_language = ? WHERE farmer_id = ?",
            (changes.farmer_name, changes.preferred_language, row["farmer_id"]),
        )
        conn.execute(
            """UPDATE crops SET crop_type = ?, variety = ?, sowing_date = ?, area_acres = ?,
                                location_name = ?, latitude = ?, longitude = ?, stage = ?,
                                updated_at = datetime('now')
               WHERE crop_id = ?""",
            (changes.crop_type, changes.variety or None, changes.sowing_date.isoformat(),
             changes.area_acres, changes.location_name, lat, lon, changes.stage.value, crop_id),
        )
    return get_crop(crop_id)


# ---------------------------------------------------------------------------
# F1–F4 — analyses
# ---------------------------------------------------------------------------

def save_analysis(result: AnalysisResult) -> AnalysisResult:
    with connect() as conn:
        conn.execute(
            """INSERT INTO analyses (analysis_id, crop_id, created_at, top_label, risk_level, is_demo, result_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (result.analysis_id, result.crop_id, result.created_at.isoformat(),
             result.predictions[0].label, result.risk.level.value, int(result.is_demo),
             result.model_dump_json()),
        )
    return result


def list_analyses(crop_id: str, limit: int = 50) -> list[AnalysisResult]:
    """Analyses for a crop, newest first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT result_json FROM analyses WHERE crop_id = ? ORDER BY created_at DESC LIMIT ?",
            (crop_id, limit),
        ).fetchall()
    return [AnalysisResult.model_validate_json(r["result_json"]) for r in rows]


# ---------------------------------------------------------------------------
# F5 — loans (MOCK data only)
# ---------------------------------------------------------------------------

def get_loan_summary(crop_id: str) -> LoanSummary | None:
    """Loan summary for the farmer who owns this crop, or None if they have
    no loan records. `missing_document_codes` is computed from the checklist."""
    with connect() as conn:
        loan = conn.execute(
            """SELECT l.* FROM loans l JOIN crops c ON c.farmer_id = l.farmer_id
               WHERE c.crop_id = ? ORDER BY l.loan_id LIMIT 1""",
            (crop_id,),
        ).fetchone()
        if loan is None:
            return None
        docs = conn.execute(
            "SELECT code, name_json, submitted FROM loan_documents WHERE loan_id = ? ORDER BY position",
            (loan["loan_id"],),
        ).fetchall()

    documents = [
        DocumentItem(code=d["code"], name=LocalizedText.model_validate_json(d["name_json"]), submitted=bool(d["submitted"]))
        for d in docs
    ]
    next_repayment = None
    if loan["next_due_date"] is not None:
        next_repayment = RepaymentDue(due_date=loan["next_due_date"], amount_inr=loan["next_due_amount_inr"])
    return LoanSummary(
        data_source=loan["data_source"],
        crop_id=crop_id,
        loan=Loan(
            loan_id=loan["loan_id"],
            loan_type=loan["loan_type"],
            display_name=LocalizedText.model_validate_json(loan["display_name_json"]),
            lender_name=loan["lender_name"],
            status=loan["status"],
            sanctioned_amount_inr=loan["sanctioned_amount_inr"],
            outstanding_amount_inr=loan["outstanding_amount_inr"],
            next_repayment=next_repayment,
        ),
        documents=documents,
        missing_document_codes=[d.code for d in documents if not d.submitted],
        schemes=schemes_for(loan["loan_type"]),
    )


def schemes_for(loan_type: str) -> list[Scheme]:
    """Schemes worth checking for a loan type (shared/content/schemes.json)."""
    content = load("schemes")
    return [
        Scheme(code=code, **content["schemes"][code])
        for code in content["by_loan_type"].get(loan_type, [])
    ]


def set_document_submitted(crop_id: str, code: str, submitted: bool) -> LoanSummary | None:
    """Mark one checklist document as submitted / not submitted for the loan
    of the farmer who owns this crop. Returns the updated summary, or None if
    the farmer has no loan or the document code isn't on the checklist."""
    with connect() as conn:
        updated = conn.execute(
            """UPDATE loan_documents SET submitted = ?
               WHERE code = ? AND loan_id = (
                   SELECT l.loan_id FROM loans l JOIN crops c ON c.farmer_id = l.farmer_id
                   WHERE c.crop_id = ? ORDER BY l.loan_id LIMIT 1)""",
            (int(submitted), code, crop_id),
        ).rowcount
    return get_loan_summary(crop_id) if updated else None


# ---------------------------------------------------------------------------
# Demo seed
# ---------------------------------------------------------------------------

DEMO_FARMER_ID = "farmer-demo-001"


def seed_demo_if_empty() -> bool:
    """Insert the demo farmer, crop, analysis and MOCK loan from
    shared/sample_data.json if the database has no crops yet.
    Returns True if it seeded. Safe to call on every startup."""
    with connect() as conn:
        if conn.execute("SELECT 1 FROM crops LIMIT 1").fetchone():
            return False

    demo = sample()
    p = demo.crop_profile
    with connect() as conn:
        conn.execute(
            "INSERT INTO farmers (farmer_id, name, preferred_language) VALUES (?, ?, ?)",
            (DEMO_FARMER_ID, p.farmer_name, p.preferred_language),
        )
        conn.execute(
            """INSERT INTO crops (crop_id, farmer_id, crop_type, variety, sowing_date, area_acres,
                                  location_name, latitude, longitude, stage,
                                  expected_harvest_start, expected_harvest_end, yield_min_kg, yield_max_kg)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p.crop_id, DEMO_FARMER_ID, p.crop_type, p.variety, p.sowing_date.isoformat(), p.area_acres,
             p.location.name, p.location.latitude, p.location.longitude, p.stage.value,
             p.expected_harvest_start and p.expected_harvest_start.isoformat(),
             p.expected_harvest_end and p.expected_harvest_end.isoformat(),
             p.yield_estimate and p.yield_estimate.min_kg, p.yield_estimate and p.yield_estimate.max_kg),
        )
        ls = demo.loan_summary
        loan = ls.loan
        conn.execute(
            """INSERT INTO loans (loan_id, farmer_id, loan_type, display_name_json, lender_name, status,
                                  sanctioned_amount_inr, outstanding_amount_inr,
                                  next_due_date, next_due_amount_inr, data_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (loan.loan_id, DEMO_FARMER_ID, loan.loan_type, loan.display_name.model_dump_json(),
             loan.lender_name, loan.status.value, loan.sanctioned_amount_inr, loan.outstanding_amount_inr,
             loan.next_repayment and loan.next_repayment.due_date.isoformat(),
             loan.next_repayment and loan.next_repayment.amount_inr, ls.data_source),
        )
        # Checklist from shared/content/loan_documents.json; which ones are
        # already submitted comes from the sample (land record + photo missing).
        submitted = {d.code: d.submitted for d in ls.documents}
        checklist = load("loan_documents")[loan.loan_type]
        conn.executemany(
            "INSERT INTO loan_documents (loan_id, code, name_json, submitted, position) VALUES (?, ?, ?, ?, ?)",
            [(loan.loan_id, d["code"], LocalizedText(**d["name"]).model_dump_json(), int(submitted.get(d["code"], False)), i)
             for i, d in enumerate(checklist)],
        )
    save_analysis(demo.analysis)
    return True

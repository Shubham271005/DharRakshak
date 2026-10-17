"""
Validate `shared/sample_data.json` against the data contract.

Run from the repository root:
    python scripts/check_sample_data.py

Run this every time you change `shared/contract.py` or `shared/sample_data.json`.
If it prints "OK", the frontend mocks and the backend contract agree.
"""

import json
import sys
from pathlib import Path

# Make the repo root importable so `import shared...` works when run as a script.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError  # noqa: E402

from shared.contract import REQUIRED_LANGUAGES, SampleData  # noqa: E402

SAMPLE_PATH = REPO_ROOT / "shared" / "sample_data.json"


def main() -> int:
    raw = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))

    try:
        data = SampleData.model_validate(raw)
    except ValidationError as err:
        print("FAILED — sample_data.json does not match shared/contract.py:\n")
        print(err)
        return 1

    # Short human-readable summary so you can eyeball the result.
    a, loan = data.analysis, data.loan_summary
    print("OK — sample_data.json matches the contract")
    print(f"  languages required : {', '.join(REQUIRED_LANGUAGES)}")
    print(f"  crop               : {data.crop_profile.crop_type} ({data.crop_profile.stage.value}), "
          f"day {data.crop_profile.days_since_sowing}")
    print(f"  top prediction     : {a.predictions[0].display_name.en} ({a.predictions[0].confidence:.2f})")
    print(f"  risk               : {a.risk.level.value} (score {a.risk.score}, estimate)")
    print(f"  action cards       : {len(a.action_cards)}")
    print(f"  loan               : {loan.loan.display_name.en}, data_source={loan.data_source}")
    print(f"  missing documents  : {', '.join(loan.missing_document_codes)}")
    print(f"  chat examples      : {len(data.chat_examples)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

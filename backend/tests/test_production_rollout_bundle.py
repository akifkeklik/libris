"""The one-paste rollout bundle must stay identical to the numbered migrations it is made of."""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
SCRIPTS = Path(__file__).parent.parent / "scripts"


@pytest.mark.parametrize("number", ["09", "10", "13", "16", "17", "18", "19", "20"])
def test_bundle_contains_the_current_migration(number):
    bundle = (SCRIPTS / "ops" / "production_rollout.sql").read_text(encoding="utf-8")
    source = next(SCRIPTS.glob(f"{number}_*.sql")).read_text(encoding="utf-8")
    assert re.sub(r"(?mi)^\s*(BEGIN|COMMIT)\s*;\s*$", "", source).strip() in bundle


def test_bundle_is_one_transaction():
    bundle = (SCRIPTS / "ops" / "production_rollout.sql").read_text(encoding="utf-8")
    assert len(re.findall(r"(?m)^BEGIN;", bundle)) == len(re.findall(r"(?m)^COMMIT;", bundle)) == 1

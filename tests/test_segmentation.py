"""
Automated checks for the segmentation and the Power BI export.

Run from the project folder with:
    pytest tests/
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.segmentation import PERSONAS, fit, powerbi_tables  # noqa: E402

PBI = ROOT / "powerbi"


@pytest.fixture(scope="module")
def result():
    return fit(str(ROOT / "data"))


@pytest.fixture(scope="module")
def exported():
    return {name: pd.read_csv(PBI / "data" / f"{name}.csv")
            for name in ["customers", "segments", "metrics", "segment_profile", "k_selection"]}


def test_segment_sizes_match_notebook(result):
    sizes = result.data["segment_name"].value_counts().to_dict()
    assert sizes == {"Cash-advance reliant": 2390, "Light users": 1551, "High-limit spenders": 1532,
                     "Transactors": 1239, "Near-limit revolvers": 1153, "Heavy all-rounders": 1084}


def test_every_persona_used_once(result):
    assert sorted(result.names.values()) == sorted(PERSONAS)


def test_naming_rules_hold(result):
    med = result.data.groupby("segment_name")[["PRC_FULL_PAYMENT", "utilization", "PURCHASES", "CASH_ADVANCE"]].median()
    assert med["PRC_FULL_PAYMENT"].idxmax() == "Transactors"
    assert med["utilization"].idxmax() == "Near-limit revolvers"
    assert med.loc["Cash-advance reliant", "PURCHASES"] == 0


def test_module_reproduces_exported_tables(result, exported):
    """The notebook wrote powerbi/data; the module must produce the same tables."""
    tables = powerbi_tables(result)
    for name in ["customers", "segments", "metrics", "segment_profile"]:
        pd.testing.assert_frame_equal(tables[name].reset_index(drop=True), exported[name],
                                      check_dtype=False, atol=1e-3, obj=name)


def test_star_schema_keys(exported):
    c, s, m, p = exported["customers"], exported["segments"], exported["metrics"], exported["segment_profile"]
    assert c["customer_id"].is_unique and s["segment_id"].is_unique and m["metric_id"].is_unique
    assert set(c["segment_id"]) == set(s["segment_id"])
    assert set(p["segment_id"]) <= set(s["segment_id"]) and set(p["metric_id"]) <= set(m["metric_id"])
    assert len(p) == len(s) * len(m)
    assert s["customers"].sum() == len(c) == 8949


def test_theme_is_valid_json():
    theme = json.loads((PBI / "DataKritii_theme.json").read_text(encoding="utf-8"))
    assert theme["name"] == "DataKritii" and len(theme["dataColors"]) >= 6


def test_guide_only_uses_defined_measures():
    """Every measure the build guide asks for must exist in measures.dax."""
    dax = (PBI / "measures.dax").read_text(encoding="utf-8")
    defined = set(re.findall(r"^([A-Z%][^\n=/]*?) =", dax, flags=re.M))
    guide = (PBI / "POWERBI_BUILD_GUIDE.md").read_text(encoding="utf-8")
    referenced = {m for m in re.findall(r"`([^`]+)`", guide) if m in {d.strip() for d in defined} or m.startswith(
        ("Profile ", "Selected", "Selection", "Share of", "Median Util", "% ", "Avg ", "Segment Color", "Customers", "Segments"))}
    missing = {r for r in referenced if r not in {d.strip() for d in defined}}
    assert not missing, missing

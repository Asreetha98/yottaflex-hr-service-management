"""Generator tests (starter size for speed): reproducibility, ground-truth separation, anomaly labels, validation."""

import os
import tempfile

import pytest

from generator.generate import STARTER, run
from validation.report_generator import validate

ANOMALY_TYPES = 13


@pytest.fixture(scope="module")
def starter_run():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        first = run(os.path.join(a, "o"), STARTER)
        second = run(os.path.join(b, "o"), STARTER)
        result = validate(os.path.join(a, "o"), {"tickets": STARTER.tickets, "messages": STARTER.messages})
        yield first, second, result, os.path.join(a, "o")


def test_row_counts_exact(starter_run):
    first = starter_run[0]["files"]
    assert first["tickets.csv"]["rows"] == STARTER.tickets
    assert first["messages.csv"]["rows"] == STARTER.messages
    assert first["policy_documents.csv"]["rows"] == 24


def test_generation_is_reproducible(starter_run):
    first, second = starter_run[0]["files"], starter_run[1]["files"]
    assert first == second


def test_all_13_anomaly_types_present(starter_run):
    by_type = starter_run[0]["anomalies_by_type"]
    assert len(by_type) == ANOMALY_TYPES
    assert all(n >= 1 for n in by_type.values())
    for mandatory in ("OBSOLETE_POLICY_CITATION", "SENSITIVE_IN_GENERAL_QUEUE",
                      "SLA_EXCLUDES_BUSINESS_HOURS", "UNSUPPORTED_CLAIM_AS_VERIFIED"):
        assert mandatory in by_type


def test_ground_truth_separate_from_operational_tables(starter_run):
    out = starter_run[3]
    header = open(os.path.join(out, "tickets.csv"), encoding="utf-8").readline()
    assert "expected_category" not in header
    assert "anomaly" not in header
    assert os.path.exists(os.path.join(out, "ground_truth.json"))
    assert os.path.exists(os.path.join(out, "ground_truth.csv"))


def test_validators_find_every_injected_anomaly_and_nothing_else(starter_run):
    result = starter_run[2]
    assert result["missed"] == []
    assert result["unintended"] == []
    assert result["passed"]

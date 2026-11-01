"""Deterministic rule-engine tests: classification, sensitive routing, clarification, SLA, policy validity."""

from datetime import date, datetime, timezone

import pytest

from app.rules.classification_engine import ClassificationEngine
from app.rules.clarification_engine import ClarificationEngine
from app.rules.sensitive_routing_engine import SensitiveRoutingEngine
from app.rules.sla_engine import BusinessCalendar, BusinessHoursCalculator, calculate_sla_deadline, derive_priority
from app.constants import ALLOWED_TRANSITIONS

CLASSIFY = ClassificationEngine()
SENSITIVE = SensitiveRoutingEngine()
CLARIFY = ClarificationEngine()


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


@pytest.mark.parametrize("subject,body,expected", [
    ("Payslip missing", "My salary payslip for this month is missing", "PAYROLL"),
    ("Annual leave", "I want to apply for annual leave next week", "LEAVE"),
    ("Health insurance", "How do I add my spouse to my health insurance plan", "BENEFITS"),
    ("New joiner laptop", "I am a new hire starting Monday, what documents for onboarding are needed", "ONBOARDING"),
])
def test_classification_categories(subject, body, expected):
    assert CLASSIFY.classify(subject, body).category == expected


def test_classification_is_deterministic():
    a = CLASSIFY.classify("Payslip", "salary payslip missing").to_dict()
    b = CLASSIFY.classify("Payslip", "salary payslip missing").to_dict()
    assert a == b


def test_classification_explains_decision():
    result = CLASSIFY.classify("Payslip missing", "My salary payslip is missing")
    assert result.to_dict()["decision_explanation"]
    assert result.to_dict()["matched_rules"]


@pytest.mark.parametrize("text", [
    "I want to report harassment by my manager",
    "I need to file a grievance about discrimination",
])
def test_sensitive_detection_positive(text):
    assert SENSITIVE.detect("Confidential matter", text).is_sensitive


def test_sensitive_detection_negative():
    assert not SENSITIVE.detect("Payslip", "My payslip is missing").is_sensitive


def test_sensitive_priority_is_raised():
    assert derive_priority("harassment complaint", "please help", True) in ("P1", "P2")


def test_clarification_for_vague_ticket():
    result = CLASSIFY.classify("Leave", "I need leave")
    decision = CLARIFY.needs_clarification("Leave", "I need leave", result, False)
    assert decision.needs_clarification is True
    assert decision.message


def test_no_clarification_when_complete():
    text = "I want annual leave from 3 November to 7 November 2026"
    result = CLASSIFY.classify("Annual leave request", text)
    decision = CLARIFY.needs_clarification("Annual leave request", text, result, False)
    assert decision.needs_clarification is False


def test_business_hours_exclude_weekend():
    calc = BusinessHoursCalculator(BusinessCalendar.from_values())
    friday_4pm = utc(2026, 10, 23, 16, 0)  # Friday
    due = calc.add_business_minutes(friday_4pm, 120)
    assert due == utc(2026, 10, 26, 10, 0)  # Monday 10:00 (1h Friday + 1h Monday)


def test_business_hours_skip_holiday():
    calc = BusinessHoursCalculator(BusinessCalendar.from_values(holidays=[date(2026, 10, 26)]))
    due = calc.add_business_minutes(utc(2026, 10, 23, 16, 0), 120)
    assert due == utc(2026, 10, 27, 10, 0)


def test_elapsed_business_minutes_roundtrip():
    calc = BusinessHoursCalculator(BusinessCalendar.from_values())
    start = utc(2026, 10, 21, 10, 0)
    assert calc.elapsed_business_minutes(start, calc.add_business_minutes(start, 600)) == 600


def test_sla_deadline_not_wall_clock():
    cal = BusinessCalendar.from_values()
    start = utc(2026, 10, 23, 15, 0)
    deadline = calculate_sla_deadline(start, "PAYROLL", "P3", False, None, cal)
    wall = start.timestamp() + deadline.target_hours * 3600
    assert deadline.due_at.timestamp() > wall  # weekend/after-hours time is excluded


def test_lifecycle_closed_is_terminal():
    assert ALLOWED_TRANSITIONS["CLOSED"] == ()
    assert ALLOWED_TRANSITIONS["CANCELLED"] == ()
    assert "IN_PROGRESS" not in ALLOWED_TRANSITIONS["CLOSED"]
    assert "CLOSED" in ALLOWED_TRANSITIONS["RESOLVED"]

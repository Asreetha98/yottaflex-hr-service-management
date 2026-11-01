"""Policy documents, versions (with realistic version chains), audiences and citations.

Scenarios give the validity engine something to chew on:

* ``single``   one published version, open ended
* ``two``      v1 archived, v2 published (v2 supersedes v1 on a change date)
* ``draft``    as ``two`` plus a v3 DRAFT that is the *latest created* but not in force
* ``future``   as ``two`` plus a v3 PUBLISHED that only becomes effective on 2026-12-01
* ``audience`` as ``two`` but v2 only targets US/UK employees
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from generator.config import stage_rng
from generator.master_data.departments import sd, ts
from generator.utils.dataset import Dataset
from generator.utils.id_generator import policy_id as make_policy_id, version_id as make_version_id

# category -> topics: (title, topic_key, entitlement sentence, (v1, v2, v3) values)
TOPICS: Dict[str, Tuple[Tuple[str, str, str, Tuple[str, str, str]], ...]] = {
    "PAYROLL": (
        ("Salary Payment Schedule", "salary payment date",
         "Salaries are credited to the employee's bank account on {v}.",
         ("the 28th of each month", "the last working day of each month", "the 25th of each month")),
        ("Payslip Access and Corrections", "payslip",
         "Payslips are published in the employee portal within {v} after payroll close.",
         ("3 working days", "2 working days", "1 working day")),
        ("Tax Withholding and Deductions", "tax deduction",
         "Employees may submit a revised tax declaration up to {v} before payroll cut-off.",
         ("10 days", "7 days", "5 days")),
        ("Expense Reimbursement", "expense reimbursement",
         "Expense claims must be submitted within {v} of the expense date.",
         ("30 days", "45 days", "60 days")),
        ("Overtime Compensation", "overtime pay",
         "Approved overtime is paid at {v} the base hourly rate.",
         ("1.25 times", "1.5 times", "1.75 times")),
        ("Bonus and Increment Cycle", "bonus and increment",
         "Annual bonus and increment decisions are communicated by {v}.",
         ("31 March", "15 March", "28 February")),
    ),
    "LEAVE": (
        ("Annual Leave Entitlement", "annual leave",
         "Full-time employees accrue {v} of annual leave per calendar year.",
         ("18 days", "20 days", "22 days")),
        ("Sick Leave", "sick leave",
         "Employees are entitled to {v} of paid sick leave per year.",
         ("8 days", "10 days", "12 days")),
        ("Parental Leave", "parental leave",
         "Primary caregivers may take up to {v} of paid parental leave.",
         ("12 weeks", "16 weeks", "18 weeks")),
        ("Bereavement Leave", "bereavement leave",
         "Employees may take {v} of paid bereavement leave for an immediate family member.",
         ("3 days", "5 days", "7 days")),
        ("Leave Carry Forward", "leave carry forward",
         "Up to {v} of unused annual leave may be carried into the next year.",
         ("5 days", "10 days", "7 days")),
        ("Sabbatical Leave", "sabbatical",
         "Employees with {v} of service may apply for an unpaid sabbatical.",
         ("7 years", "5 years", "4 years")),
    ),
    "BENEFITS": (
        ("Health Insurance Coverage", "health insurance",
         "The company pays {v} of the employee health insurance premium.",
         ("70 percent", "80 percent", "85 percent")),
        ("Dental and Vision Plans", "dental and vision",
         "Dental and vision cover can be enrolled within {v} of joining or during open enrollment.",
         ("30 days", "45 days", "60 days")),
        ("Retirement Plan 401k Match", "401k match",
         "The company matches employee 401k contributions up to {v} of salary.",
         ("3 percent", "4 percent", "5 percent")),
        ("Wellness Allowance", "wellness allowance",
         "Each employee receives an annual wellness allowance of {v}.",
         ("200 dollars", "300 dollars", "500 dollars")),
        ("Dependent Coverage", "dependent coverage",
         "Dependents can be added within {v} of a qualifying life event.",
         ("20 days", "30 days", "45 days")),
        ("FSA and HSA Accounts", "fsa and hsa",
         "The annual employee contribution limit for health savings accounts is {v}.",
         ("3000 dollars", "3300 dollars", "3600 dollars")),
    ),
    "ONBOARDING": (
        ("Pre-Joining Documentation", "joining documents",
         "New hires must return signed joining documents {v} before the start date.",
         ("3 working days", "5 working days", "7 working days")),
        ("Background Verification", "background check",
         "Background verification is completed within {v} of consent.",
         ("10 working days", "7 working days", "5 working days")),
        ("Orientation and Induction", "orientation",
         "The induction programme runs for {v} starting on the first day.",
         ("1 day", "2 days", "3 days")),
        ("Probation Period", "probation",
         "The standard probation period is {v}.",
         ("6 months", "3 months", "4 months")),
        ("Employment Contract and Letters", "employment letter",
         "Employment letters are issued within {v} of a written request.",
         ("5 working days", "3 working days", "2 working days")),
        ("Equipment Provisioning", "equipment provisioning",
         "Laptops and access cards are ready {v} before the start date.",
         ("1 day", "2 days", "3 days")),
    ),
}
CATEGORY_ORDER = ("PAYROLL", "LEAVE", "BENEFITS", "ONBOARDING")
SCENARIOS = ("two", "draft", "future", "two", "single", "audience", "two", "draft")


def _dt(day: date, hour: int = 10) -> datetime:
    return datetime(day.year, day.month, day.day, hour, 0, 0, tzinfo=timezone.utc)


def _content(title: str, sentence: str, version_number: int) -> str:
    return (
        "%s (version %d)\n"
        "1. Purpose\n1.1 This policy explains the rules that apply to %s at YottaFlex AI.\n"
        "2. Entitlement\n2.1 %s\n"
        "3. Process\n3.1 Requests are raised through the HR service portal and handled by the responsible HR team.\n"
        "4. Exceptions\n4.1 Exceptions require written approval from the HR Business Partner."
        % (title, version_number, title.lower(), sentence)
    )


def generate_policies(ds: Dataset) -> None:
    rng = stage_rng("policies")
    categories = ds.extra["category_ids"]
    versions_meta: List[Dict[str, Any]] = []
    policy_info: Dict[str, Dict[str, Any]] = {}
    audience_no = 0
    citation_no = 0
    policy_no = 0
    admin_user = "USR-000001"

    for category in CATEGORY_ORDER:
        for title, topic, template, values in TOPICS[category]:
            policy_no += 1
            if policy_no > ds.size.policies:
                break
            pid = make_policy_id(policy_no)
            scenario = SCENARIOS[(policy_no - 1) % len(SCENARIOS)]
            retired = policy_no == ds.size.policies and ds.size.policies >= 24
            ds.add("policy_documents", policy_id=pid, title=title,
                   description="Official policy on %s" % topic, category_id=categories[category],
                   owner_department_id="DEPT-01", status="RETIRED" if retired else "ACTIVE",
                   created_at=_dt(date(2024, 11, 1)), updated_at=_dt(date(2024, 11, 1)), **sd())
            policy_info[pid] = {"category": category, "scenario": scenario, "topic": topic,
                                "retired": retired, "title": title}

            change = date(2026, 3, 1) + timedelta(days=rng.randint(0, 150))
            plan: List[Dict[str, Any]] = []
            if scenario == "single":
                plan.append(dict(n=1, status="PUBLISHED", frm=date(2025, 1, 1), to=None))
            else:
                plan.append(dict(n=1, status="ARCHIVED", frm=date(2025, 1, 1), to=change - timedelta(days=1)))
                v2_to = date(2026, 11, 30) if scenario == "future" else None
                plan.append(dict(n=2, status="PUBLISHED", frm=change, to=v2_to))
                if scenario == "draft":
                    plan.append(dict(n=3, status="DRAFT", frm=None, to=None))
                if scenario == "future":
                    plan.append(dict(n=3, status="PUBLISHED", frm=date(2026, 12, 1), to=None))

            previous: Optional[str] = None
            for spec in plan:
                n = spec["n"]
                vid = make_version_id(pid, n)
                sentence = template.format(v=values[n - 1])
                if spec["status"] == "DRAFT":
                    published_at = None
                    created = _dt(date(2026, 9, 15))
                elif n == 3:  # future-dated publication
                    published_at = _dt(date(2026, 10, 1))
                    created = _dt(date(2026, 9, 20))
                else:
                    published_at = _dt(spec["frm"] - timedelta(days=10))
                    created = _dt(spec["frm"] - timedelta(days=15), 9)
                audiences: List[Tuple[str, Optional[str]]] = [("ALL", None)]
                if scenario == "audience" and n >= 2:
                    audiences = [("LOCATION", "US"), ("LOCATION", "UK")]
                ds.add("policy_versions", version_id=vid, policy_id=pid, version_number=n,
                       title=title, content=_content(title, sentence, n), summary=sentence,
                       status=spec["status"], effective_from=spec["frm"], effective_to=spec["to"],
                       published_at=published_at, published_by=admin_user if published_at else None,
                       created_by=admin_user, supersedes_version_id=previous,
                       created_at=created, updated_at=created, **sd())
                for kind, value in audiences:
                    audience_no += 1
                    ds.add("policy_audiences", audience_id="AUD-%06d" % audience_no, version_id=vid,
                           audience_type=kind, audience_value=value, created_at=created, updated_at=created)
                citation_no += 1
                ds.add("policy_citations", citation_id="CIT-%06d" % citation_no, version_id=vid,
                       article_id=None, section_reference="Section 2.1", excerpt=sentence,
                       created_at=created, updated_at=created)
                versions_meta.append(dict(
                    version_id=vid, policy_id=pid, version_number=n, status=spec["status"],
                    effective_from=spec["frm"], effective_to=spec["to"], published_at=published_at,
                    created_at=created, audiences=tuple(audiences), title=title, category=category,
                    sentence=sentence, topic=topic, scenario=scenario, retired=retired,
                ))
                previous = vid

    ds.extra["version_meta"] = versions_meta
    ds.extra["policy_info"] = policy_info
    ds.extra["citation_counter"] = citation_no

"""Categories plus the configurable rule tables (classification, routing, clarification)."""

from typing import Dict

from generator.master_data.departments import sd, ts
from generator.utils.dataset import Dataset
from app.rules.clarification_engine import DEFAULT_TEMPLATES
from app.rules.classification_engine import DEFAULT_RULES
from app.rules.routing_engine import DEFAULT_ROUTING_RULES

CATEGORIES = (
    ("CAT-01", "PAYROLL", "Payroll"),
    ("CAT-02", "LEAVE", "Leave"),
    ("CAT-03", "BENEFITS", "Benefits"),
    ("CAT-04", "ONBOARDING", "Onboarding"),
    ("CAT-05", "IT", "IT Support"),
    ("CAT-06", "GENERAL", "General"),
)


def generate_categories(ds: Dataset) -> None:
    for cat_id, code, name in CATEGORIES:
        ds.add("categories", category_id=cat_id, code=code, name=name,
               description="%s requests" % name, is_active=True, **ts(), **sd())
    codes: Dict[str, str] = {code: cat_id for cat_id, code, _ in CATEGORIES}
    ds.extra["category_ids"] = codes


def generate_rules(ds: Dataset) -> None:
    codes = ds.extra["category_ids"]
    number = 0
    for rule in DEFAULT_RULES:
        for term, rule_type, weight in rule.iter_terms():
            number += 1
            ds.add("category_rules", rule_id="CRL-%06d" % number, category_id=codes[rule.category],
                   rule_type=rule_type, term=term, weight=weight, is_active=True, **ts(), **sd())

    teams = {(t["team_type"], t["support_level"]): t["team_id"] for t in ds.rows("teams")}
    for rule in DEFAULT_ROUTING_RULES:
        ds.add("routing_rules", rule_id=rule.rule_id, name=rule.name,
               category_id=codes.get(rule.category) if rule.category else None,
               is_sensitive=rule.is_sensitive, priority_order=rule.priority_order,
               target_team_id=teams[(rule.target_team, rule.support_level)], description=rule.name,
               is_active=True, **ts(), **sd())

    for index, tpl in enumerate(DEFAULT_TEMPLATES, start=1):
        ds.add("clarification_templates", template_id="CLT-%02d" % index, category_id=codes[tpl.category],
               required_field=tpl.required_field, question_text=tpl.question_text,
               detection_keywords=list(tpl.detection_keywords), display_order=tpl.display_order,
               is_active=True, **ts(), **sd())


def generate_categories_and_rules(ds: Dataset) -> None:
    generate_categories(ds)
    generate_rules(ds)

"""Build ground truth: per-ticket expected outcomes plus the anomaly register.

Ground truth is derived from the generator's own labels (``plan["truth"]``), never from the
rule engines under test, and is written to files separate from the operational tables.
"""

from typing import Any, Dict, List

from generator.utils.dataset import Dataset


def build_ground_truth(ds: Dataset, anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
    ambiguous = {a["ticket_id"] for a in anomalies if a["anomaly_type"] == "AMBIGUOUS_CLASSIFICATION"}
    anomaly_by_ticket: Dict[str, List[str]] = {}
    for a in anomalies:
        if a["ticket_id"]:
            anomaly_by_ticket.setdefault(a["ticket_id"], []).append(a["anomaly_type"])
    rows = []
    for plan in ds.extra["plans"]:
        truth = plan["truth"]
        tid = plan["ticket_id"]
        is_amb = tid in ambiguous
        rows.append({
            "ticket_id": tid,
            "expected_category": None if is_amb else truth["expected_category"],
            "expected_sensitive": bool(truth["expected_sensitive"]),
            "expected_clarification": True if is_amb else bool(truth["expected_clarification"]),
            "scenario_kind": truth.get("kind"),
            "anomaly_types": ";".join(sorted(anomaly_by_ticket.get(tid, []))),
        })
    rows.sort(key=lambda r: r["ticket_id"])
    return {"tickets": rows, "anomalies": anomalies}

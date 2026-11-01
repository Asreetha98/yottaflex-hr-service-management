"""Dataset generator entrypoint.

    python -m generator.generate --output generator/output --size full --seed 20261022
"""

import argparse
import json
import os
import sys
from dataclasses import replace
from typing import Any, Dict

from generator import config
from generator.anomaly_injection.inject import inject_anomalies
from generator.ground_truth.build import build_ground_truth
from generator.master_data.categories import generate_categories_and_rules
from generator.master_data.departments import generate_organisation
from generator.master_data.employees import generate_employees
from generator.master_data.knowledge import generate_knowledge
from generator.master_data.policies import generate_policies
from generator.transaction_data.tickets import generate_tickets
from generator.utils.dataset import COLUMNS, Dataset, sha256_file, write_csv, write_dataset, write_json

STARTER = config.DatasetSize(tickets=200, messages=800, articles=30, employees=60, policies=24,
                             anomalies_per_type=2, login_events=100)


def build(size: config.DatasetSize) -> Dataset:
    ds = Dataset(size)
    for stage in (generate_organisation, generate_categories_and_rules, generate_employees,
                  generate_policies, generate_knowledge, generate_tickets):
        stage(ds)
    return ds


def run(output: str, size: config.DatasetSize) -> Dict[str, Any]:
    ds = build(size)
    anomalies = inject_anomalies(ds)
    truth = build_ground_truth(ds, anomalies)

    manifest = write_dataset(ds, output)
    write_json(os.path.join(output, "ground_truth.json"), truth)
    write_csv(os.path.join(output, "ground_truth.csv"),
              ["ticket_id", "expected_category", "expected_sensitive", "expected_clarification",
               "scenario_kind", "anomaly_types"], truth["tickets"])
    write_csv(os.path.join(output, "anomaly_register.csv"),
              ["issue_id", "anomaly_type", "entity_type", "entity_id", "ticket_id", "severity", "mandatory", "label",
               "description", "expected_behaviour", "injected_condition"], anomalies)
    for name in ("ground_truth.json", "ground_truth.csv", "anomaly_register.csv"):
        path = os.path.join(output, name)
        rows = len(truth["tickets"]) if name.startswith("ground_truth") else len(anomalies)
        manifest[name] = {"rows": rows, "sha256": sha256_file(path)}
    summary = {"seed": config.SEED, "reference_now": config.REFERENCE_NOW.isoformat(), "files": manifest,
               "anomalies_by_type": {}}
    for a in anomalies:
        summary["anomalies_by_type"][a["anomaly_type"]] = summary["anomalies_by_type"].get(a["anomaly_type"], 0) + 1
    write_json(os.path.join(output, "manifest.json"), summary)
    return summary


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the YottaFlex AI HR dataset")
    parser.add_argument("--output", default=config.DEFAULT_OUTPUT_DIR)
    parser.add_argument("--size", choices=("full", "starter"), default="full")
    parser.add_argument("--seed", type=int, default=config.SEED)
    args = parser.parse_args(argv)
    if args.seed != config.SEED:
        print("Only the fixed seed %d is supported for the documented checksums." % config.SEED, file=sys.stderr)
        return 2
    size = config.FULL_SIZE if args.size == "full" else STARTER
    summary = run(args.output, size)
    print(json.dumps({"tables": {k: v["rows"] for k, v in summary["files"].items()},
                      "anomalies_by_type": summary["anomalies_by_type"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

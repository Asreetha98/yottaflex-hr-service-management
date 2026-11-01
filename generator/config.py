"""Generator configuration: fixed seed, dataset sizes and the reference clock."""

import os
import random
from dataclasses import dataclass
from datetime import date, datetime, timezone

SEED = 20261022
REFERENCE_DATE = date(2026, 10, 22)
REFERENCE_NOW = datetime(2026, 10, 22, 17, 0, 0, tzinfo=timezone.utc)
DATA_START_DATE = date(2026, 1, 5)
MASTER_CREATED_AT = datetime(2025, 12, 1, 9, 0, 0, tzinfo=timezone.utc)

# Faker is optional and OFF by default: the built-in name pool guarantees byte-identical
# output on every machine, whereas Faker's output can change between releases.
USE_FAKER = os.environ.get("GENERATOR_USE_FAKER", "0") == "1"

DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


@dataclass(frozen=True)
class DatasetSize:
    tickets: int = 5000
    messages: int = 20000
    articles: int = 150
    employees: int = 300
    policies: int = 24
    anomalies_per_type: int = 5
    login_events: int = 1500


FULL_SIZE = DatasetSize()


def stage_rng(name: str, seed: int = SEED) -> random.Random:
    """Independent, reproducible random stream per generation stage."""
    return random.Random("%d:%s" % (seed, name))

"""Name source: Faker with a fixed seed when requested and installed, else a built-in pool.

The built-in pool is the default so output is identical everywhere.
"""

import random
from typing import Any, Optional

from generator.config import SEED

FIRST_NAMES = (
    "Aarav", "Abigail", "Adrian", "Aisha", "Alejandro", "Amelia", "Anaya", "Andrew", "Anika", "Arjun",
    "Ava", "Benjamin", "Bianca", "Brandon", "Caleb", "Camila", "Carlos", "Charlotte", "Chloe", "Daniel",
    "David", "Diana", "Elena", "Elijah", "Emily", "Ethan", "Fatima", "Felix", "Gabriel", "Grace",
    "Hannah", "Hiro", "Isabella", "Isaac", "Ishaan", "Jack", "Jasmine", "Jonas", "Julia", "Kavya",
    "Kevin", "Laura", "Leo", "Liam", "Lucas", "Maria", "Mateo", "Maya", "Mohammed", "Nadia",
    "Naveen", "Nina", "Noah", "Olivia", "Omar", "Priya", "Rahul", "Rebecca", "Riya", "Samuel",
    "Sara", "Sofia", "Sophie", "Tariq", "Thomas", "Uma", "Victor", "Wei", "Yara", "Zoe",
)
LAST_NAMES = (
    "Adams", "Ahmed", "Anderson", "Bailey", "Banerjee", "Bennett", "Brown", "Campbell", "Chen", "Clarke",
    "Cooper", "Davies", "Diaz", "Edwards", "Evans", "Fischer", "Foster", "Garcia", "Gupta", "Hall",
    "Hansen", "Harris", "Hughes", "Iyer", "Jackson", "Johnson", "Kapoor", "Khan", "Kim", "Kumar",
    "Lee", "Lopez", "Martin", "Meyer", "Miller", "Mitchell", "Mukherjee", "Murphy", "Nair", "Nguyen",
    "Patel", "Perez", "Phillips", "Reddy", "Reed", "Roberts", "Rossi", "Santos", "Schmidt", "Shah",
    "Sharma", "Singh", "Smith", "Taylor", "Thomas", "Turner", "Walker", "Ward", "White", "Wilson",
)


class NameSource:
    """Draws first/last names from a ``random.Random`` stream."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def first_name(self) -> str:
        return self._rng.choice(FIRST_NAMES)

    def last_name(self) -> str:
        return self._rng.choice(LAST_NAMES)


class FakerNameSource:
    def __init__(self, faker: Any) -> None:
        self._faker = faker

    def first_name(self) -> str:
        return str(self._faker.first_name())

    def last_name(self) -> str:
        return str(self._faker.last_name())


def get_name_source(rng: random.Random, use_faker: bool = False) -> Any:
    """Return a name source; Faker (seeded with SEED) only if requested and importable."""
    if use_faker:
        try:
            from faker import Faker  # type: ignore[import-not-found]

            Faker.seed(SEED)
            return FakerNameSource(Faker("en_US"))
        except ImportError:
            pass
    return NameSource(rng)


def get_faker(use_faker: bool = False) -> Optional[Any]:
    """Seeded Faker instance, or ``None`` when unavailable / not requested."""
    if not use_faker:
        return None
    try:
        from faker import Faker  # type: ignore[import-not-found]
    except ImportError:
        return None
    Faker.seed(SEED)
    return Faker("en_US")

"""Shared business calendar (Mon-Fri 09:00-17:00 UTC plus the seeded holidays)."""

from app.rules.sla_engine import BusinessCalendar, BusinessHoursCalculator
from generator.master_data.departments import HOLIDAYS

CALENDAR = BusinessCalendar.from_values(holidays=[day for day, _ in HOLIDAYS])
CALC = BusinessHoursCalculator(CALENDAR)

"""Ticket text templates. Every template carries its own *ground truth* labels, defined here
by the author of the template and never by running the classification engines."""

import random
from typing import Any, Dict, List, Tuple

MONTHS_PAST = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October")
MONTHS_FUTURE = ("October", "November", "December")
LEAVE_TYPES = ("annual", "sick", "paternity", "maternity", "bereavement", "casual")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")

# kind: category templates -> (subject, description, complete)
PAYROLL = (
    ("Salary not credited for {month}", "My salary for {month} has not been credited to my bank account yet. Please check the payment status.", True),
    ("Incorrect tax deduction on {month} payslip", "The tax deduction on my {month} payslip looks wrong. Could you review the calculation and correct it?", True),
    ("Expense reimbursement pending", "I submitted my expense reimbursement for travel in {month} and it is still pending approval.", True),
    ("Overtime pay missing", "My overtime pay for the {month} pay period is missing from my payslip.", True),
    ("Request for salary slip", "Please share my salary slip for {month}. I need it for a loan application.", True),
    ("Bonus payment query", "When will the bonus for {month} be paid out with my salary?", True),
    ("Direct deposit change", "I changed banks and need to update my direct deposit details before the {month} payment.", True),
    ("Salary issue", "My salary seems incorrect and I am not sure what happened with the deductions.", False),
    ("Salary credit missing", "I have not received my salary credit and need this fixed.", False),
    ("Tax question", "Why was extra tax deducted from my pay? Please explain the tax deduction.", False),
    ("Reimbursement status", "My expense reimbursement has not arrived in my account.", False),
    ("Compensation query", "I would like to understand my compensation and increment details.", False),
)
LEAVE = (
    ("Apply for {leave_type} leave", "I would like to apply for {leave_type} leave from {date} to {date2}. Please approve my leave request.", True),
    ("{leave_type} leave balance", "Can you confirm my remaining {leave_type} leave balance? I plan to take time off in {month}.", True),
    ("Cancel my leave request", "Please cancel my approved {leave_type} leave on {date}; my plans have changed.", True),
    ("Leave encashment", "I want to know if unused annual leave can be encashed at the end of {month}.", True),
    ("Carry forward leave", "How many days of annual leave can I carry forward into next year? I have 6 days left on {date}.", True),
    ("Leave policy question", "Please explain the sick leave policy and how many days I get. I was absent on {date}.", True),
    ("Leave question", "How do I apply for leave in the portal?", False),
    ("Need time off", "I need some time off soon, what is the process to follow?", False),
    ("Leave balance", "Please tell me my leave balance because I cannot see it anywhere.", False),
    ("Vacation request", "I want to request a vacation. Who approves it?", False),
)
BENEFITS = (
    ("Add dependent to health insurance", "I need to add my newborn as a dependent to my health insurance. What documents are required?", True),
    ("Dental plan coverage", "Does my dental plan cover orthodontic treatment? Please confirm the coverage details.", True),
    ("Vision plan enrollment", "I missed open enrollment for the vision plan. Can I still enroll after my change in {month}?", True),
    ("401k contribution change", "I want to change my 401k contribution percentage and check the company match.", True),
    ("Insurance claim status", "My health insurance claim from {month} is still pending. Please check the claim status.", True),
    ("Wellness program allowance", "How do I claim the wellness program allowance for my gym membership? It is part of my medical benefit.", True),
    ("Benefits question", "I have a question about my benefits and who is eligible for coverage.", False),
    ("Dependent enrollment", "How do I add a dependent? The enrollment page shows an error.", False),
    ("Coverage details", "Please send the coverage details for the company benefit package.", False),
)
ONBOARDING = (
    ("Offer letter and start date", "Please confirm my start date and send a copy of my offer letter. My joining date is {date}.", True),
    ("Background check status", "What is the status of my background check? My first day is {date}.", True),
    ("Orientation schedule", "Can you share the orientation schedule for new hires starting on {weekday}?", True),
    ("Employment letter request", "I need an employment letter for visa purposes. My joining date was {date}.", True),
    ("Probation period query", "How long is the probation period for my contract that begins {date}?", True),
    ("Onboarding help", "I am a new hire and need help with the onboarding formalities.", False),
    ("Contract question", "Where can I find my employment contract and offer letter?", False),
    ("Induction details", "Please tell me about the induction program and what to bring.", False),
)
GENERAL = (
    ("Help needed", "I need some help with something, please contact me when you can."),
    ("Question about my account", "Can someone please get back to me about my account?"),
    ("Laptop not working", "My laptop keeps crashing and I cannot connect to the VPN from home."),
    ("Office access card", "My access card does not open the door on the third floor."),
    ("Printer problem", "The printer on our floor is out of paper and toner."),
    ("Seating request", "Could I get a desk closer to my team?"),
    ("Parking permit", "Where do I apply for a parking permit at the new office?"),
)
# (subject, description, expected_category)
SENSITIVE = (
    ("Complaint about my manager", "I want to file a formal complaint about my manager. I have been bullied in meetings and feel unsafe at work.", "GENERAL"),
    ("Harassment report", "I am being harassed by a colleague and want to report it confidentially.", "GENERAL"),
    ("Discrimination concern", "I believe I was discriminated against during my last performance review.", "GENERAL"),
    ("Retaliation after raising concern", "I raised a concern and now face retaliation from my team lead. This is a hostile work environment.", "GENERAL"),
    ("Leave denied unfairly", "My manager rejected my sick leave and threatened disciplinary action. I want to raise a grievance.", "LEAVE"),
    ("Salary withheld after complaint", "My salary deduction started right after I made a complaint. I suspect retaliation and need an investigation.", "PAYROLL"),
    ("Wrongful termination", "I was told my termination was wrongful and I want to speak to someone about legal action.", "GENERAL"),
    ("Misconduct during onboarding", "A colleague showed inappropriate behaviour during my orientation and I want to report the misconduct.", "ONBOARDING"),
    ("Abuse by supervisor", "My supervisor shouts and verbally abused me in front of the team. Please keep this confidential.", "GENERAL"),
)
# Look sensitive to a keyword matcher but are not: (subject, description, expected_category)
HARD_NEGATIVE = (
    ("Confidential salary letter", "Please send my salary letter to my home address and keep the document confidential. It is for my {month} payslip.", "PAYROLL"),
    ("Notice period before termination of contract", "I am resigning and want to know the notice period before the termination of my employment.", "GENERAL"),
    ("Investigation of payslip difference", "Can someone investigate the difference between my {month} payslip and my offer letter salary?", "PAYROLL"),
    ("Complaint form for insurance", "Where can I find the complaint form for a rejected health insurance claim from {month}?", "BENEFITS"),
)
# (subject, description, expected_category, complete)
MIXED = (
    ("Sick leave pay deduction", "My salary was reduced after I took sick leave in {month}. Please check the deduction on my payslip.", "PAYROLL", True),
    ("Pay for unpaid leave", "I took unpaid leave on {date}; how does it change my salary and tax deduction?", "PAYROLL", True),
    ("Benefits enrollment as new hire", "As a new hire I need to complete my health insurance enrollment before my start date of {date}.", "BENEFITS", True),
    ("Insurance during maternity leave", "Will my health insurance coverage continue during maternity leave from {date}?", "BENEFITS", True),
    ("Joining bonus payment", "When will my joining bonus be paid? My start date is {date}.", "PAYROLL", True),
)

FILLERS = ("Thanks for your help.", "Please let me know the next steps.", "I would appreciate a quick reply.",
           "Let me know if you need anything else from me.", "")
URGENT = ("This is urgent.", "I need this resolved today.", "It is an emergency for me.")

CHANNELS = (("PORTAL", 60), ("EMAIL", 20), ("CHAT", 12), ("PHONE", 8))

# Reply a requester sends after a clarification request, by the ground-truth category.
REPLIES = {
    "PAYROLL": "It is about my salary payment for {month} pay period.",
    "LEAVE": "It is about my {leave_type} leave from {date}.",
    "BENEFITS": "It is about my health insurance coverage.",
    "ONBOARDING": "It is about onboarding and my start date of {date}.",
    "GENERAL": "It is a general request about my workplace and I would like help from HR.",
}


def weighted(rng: random.Random, options: Tuple[Tuple[str, int], ...]) -> str:
    total = sum(w for _, w in options)
    pick = rng.uniform(0, total)
    running = 0.0
    for value, weight in options:
        running += weight
        if pick <= running:
            return value
    return options[-1][0]


def slots(rng: random.Random) -> Dict[str, str]:
    d1 = rng.randint(1, 28)
    d2 = min(28, d1 + rng.randint(1, 4))
    month_future = rng.choice(MONTHS_FUTURE)
    return {
        "month": rng.choice(MONTHS_PAST),
        "leave_type": rng.choice(LEAVE_TYPES),
        "date": "%d %s" % (d1, month_future),
        "date2": "%d %s" % (d2, month_future),
        "weekday": rng.choice(WEEKDAYS),
    }


def compose(rng: random.Random, first_name: str) -> Dict[str, Any]:
    """Build one ticket's text and its ground-truth labels."""
    roll = rng.random()
    fill = slots(rng)
    sensitive = False
    expected_category = "GENERAL"
    complete = False
    kind = ""
    if roll < 0.05:
        kind = "SENSITIVE"
        subject, desc, expected_category = rng.choice(SENSITIVE)
        sensitive = True
    elif roll < 0.065:
        kind = "HARD_NEGATIVE"
        subject, desc, expected_category = rng.choice(HARD_NEGATIVE)
        complete = True
    elif roll < 0.10:
        kind = "MIXED"
        subject, desc, expected_category, complete = rng.choice(MIXED)
    elif roll < 0.20:
        kind = "GENERAL"
        subject, desc = rng.choice(GENERAL)
    else:
        weights = (("PAYROLL", 28), ("LEAVE", 32), ("BENEFITS", 22), ("ONBOARDING", 14))
        expected_category = weighted(rng, weights)
        pool = {"PAYROLL": PAYROLL, "LEAVE": LEAVE, "BENEFITS": BENEFITS, "ONBOARDING": ONBOARDING}[expected_category]
        wanted_complete = rng.random() < 0.62
        options: List[Tuple[str, str, bool]] = [t for t in pool if t[2] == wanted_complete] or list(pool)
        subject, desc, complete = rng.choice(options)
        kind = "CATEGORY"
    subject = subject.format(**fill)
    desc = desc.format(**fill)
    urgent = rng.random() < 0.10
    extra = [rng.choice(URGENT)] if urgent else []
    tail = rng.choice(FILLERS)
    if tail:
        extra.append(tail)
    if rng.random() < 0.25:
        extra.append("Regards, %s" % first_name)
    description = " ".join([desc] + extra)
    return {
        "subject": subject,
        "description": description,
        "kind": kind,
        "expected_category": expected_category,
        "expected_sensitive": sensitive,
        # A sensitive ticket is never put through clarification by design.
        "expected_clarification": (not sensitive) and ((not complete) or expected_category == "GENERAL"),
        "channel": weighted(rng, CHANNELS),
        "slots": fill,
    }

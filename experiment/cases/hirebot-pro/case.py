"""HireBot Pro: everything the agents and the lead say during a trial.

Five agents build one product at the same time. Every approach gets the same task text;
only the coordination line differs:

- N ("no channel"): nothing. Each agent only hears from its own developer.
- A ("team chat"): a shared team-chat file every agent can read and write.
- B ("midflight"): connected to Midflight, with a plan and the contracts between parts.
"""

PROJECT_B = "midflight-9854"

# agent -> its git branch
BRANCHES = {
    "t1": "t1-catalog",
    "t2": "t2-pricing",
    "t3": "t3-bookings",
    "t4": "t4-reports",
    "t5": "t5-cli",
}
MIDFLIGHT_TASK = {agent: agent.upper() for agent in BRANCHES}

TASKS = {
    "t1": (
        "Your part: the catalog, in app/catalog.py. Build the API that lists the agents "
        "from README.md (handle, name, skills, hourly rate, weekly capacity), can filter "
        "them by skill, and returns one agent by its handle. Only edit app/catalog.py."
    ),
    "t2": (
        "Your part: pricing, in app/pricing.py. Build the API that prices an order (a list "
        "of agent and hours lines, with an optional promo code) by business rules 1 to 6 "
        "in README.md, and returns the itemized quote: subtotal, volume discount, promo "
        "discount, tax, and total. Only edit app/pricing.py."
    ),
    "t3": (
        "Your part: bookings, in app/bookings.py. Build the API that books an order "
        "(priced by the pricing rules, reserving hours from each agent's weekly capacity "
        "and refusing the whole booking if an agent doesn't have enough left), returns a "
        "booking by its id, cancels a booking (giving its hours back), and tells how many "
        "hours an agent has left this week. Only edit app/bookings.py."
    ),
    "t4": (
        "Your part: reports, in app/reports.py. Build the API for the revenue report: "
        "what HireBot earned, how many bookings are confirmed and cancelled, and the hours "
        "booked per agent (confirmed bookings only). Only edit app/reports.py."
    ),
    "t5": (
        "Your part: the command line, in cli/hirebot.py. Build every command in the "
        "'The command line' section of README.md, printing exactly the keys it lists. It "
        "talks to the API over HTTP (the address is in HIREBOT_URL); use only Python's "
        "standard library or httpx. Only edit cli/hirebot.py."
    ),
}

INTRO = (
    "You are one of five developers' AI agents building HireBot together (read README.md "
    "first). Each agent builds one part on its own git branch, in its own folder, at the "
    "same time; you can't see the others' work until everything is merged at the end."
)


def coordination(approach: str, agent: str, chat: str) -> str:
    if approach == "N":
        return (
            "You have no way to talk to the other agents; tell your developer anything "
            "the team should know."
        )
    if approach == "A":
        return (
            f"Team chat: the shared file {chat}. Read it before you start and before you "
            "finish; append a line starting with your part's name if you want to tell or "
            "ask the team something. The lead reads it."
        )
    task = MIDFLIGHT_TASK[agent]
    return (
        f"Your team coordinates through Midflight: project {PROJECT_B}, your task is "
        f"{task}. Your Midflight tools are connected; follow Midflight's instructions, and "
        f"pass task_id {task} and project_id {PROJECT_B} to its tools."
    )


FIRST = (
    "Build your first working version, commit it on your branch (git add, git commit), "
    "and finish with a two-line summary of what you built."
)

# Phase 2: the lead's plan change (it touches pricing, bookings, reports, and the command
# line, but not the catalog), and two developers who disagree.
LEAD_CHANGE = (
    "Message from the lead: two changes for launch. (1) Half-hour bookings: hours can be "
    "any multiple of 0.5, from 0.5 up, for example meeting-ghost=2.5. Capacity, hours "
    "left, and the report count half hours too. (2) Rush orders: adding --rush to quote "
    "or book adds a rush fee of 25% of (subtotal - volume discount - promo discount). Tax "
    "is then 8% of that amount plus the rush fee, and the total includes the rush fee. "
    "The command line prints a new line, rush_fee:, right after promo_discount: (0 when "
    "the order isn't a rush order)."
)
DEVELOPER_NOTE = {
    "t3": (
        "Note from your developer: when a booking is cancelled, refund the customer in "
        "full. We keep nothing."
    ),
    "t4": (
        "Note from your developer: a cancelled booking keeps a 20% cancellation fee, and "
        "the report counts that fee as revenue."
    ),
}
FINISH = "Update your part as needed, commit, and finish with a two-line summary."
FINISH_B = (
    "Check in with Midflight first, then update your part as needed, commit, and finish "
    "with a two-line summary."
)

# What the lead answers if anyone asks about cancellations (fixed before any trial).
LEAD_DECISION = (
    "Cancelling a booking keeps a cancellation fee of 10% of the booking's total (rounded "
    "half up); the customer is refunded the rest. The fee counts as revenue in the report."
)


def first_prompt(approach: str, agent: str, chat: str) -> str:
    return "\n\n".join([INTRO, TASKS[agent], coordination(approach, agent, chat), FIRST])


def second_prompt(approach: str, agent: str) -> str:
    parts = []
    if approach != "B":
        parts.append(LEAD_CHANGE)  # pasted into every agent's chat
    if agent in DEVELOPER_NOTE:
        parts.append(DEVELOPER_NOTE[agent])
    parts.append(FINISH_B if approach == "B" else FINISH)
    return "\n\n".join(parts)

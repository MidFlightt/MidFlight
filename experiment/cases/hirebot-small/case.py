"""Everything the agents and the lead say during a trial (docs/experiment.md).

Every approach gets the same task text. Only the coordination line differs:

- N ("no channel"): nothing. Each agent only hears from its own developer, like
  teammates whose agents run on separate laptops.
- A ("team chat"): a shared team-chat file every agent can read and write.
- B ("midflight"): connected to Midflight.
"""

PROJECT_B = "midflight-9854"

# agent -> its git branch
BRANCHES = {"t1": "t1-catalog", "t2": "t2-hiring", "t3": "t3-storefront"}

TASKS = {
    "t1": (
        "Your part: the agent catalog, in app/catalog.py. Build GET /api/agents, which "
        "returns the six agents from README.md with their id, name, tagline, and hourly "
        "rate in credits. Only edit app/catalog.py."
    ),
    "t2": (
        "Your part: hiring, in app/hiring.py. Build POST /api/hire, which takes the agents "
        "and hours a customer picks and returns a booking with its price (subtotal, the "
        "8% AI Labor Tax, and total, in credits) and a booking id; and GET "
        "/api/bookings/{id}, which returns a booking. Use the hourly rates from the "
        "catalog. Only edit app/hiring.py."
    ),
    "t3": (
        "Your part: the storefront, in web/index.html (plain HTML and JavaScript, no build "
        "step). List the agents from GET /api/agents with their hourly rates, let the "
        "customer choose hours for each agent, show the price summary, hire them with "
        "POST /api/hire, and show the booking confirmation with its id and total. Only "
        "edit web/index.html."
    ),
}

MIDFLIGHT_TASK = {"t1": "T1", "t2": "T2", "t3": "T3"}

INTRO = (
    "You are one of three developers' AI agents building HireBot together (read "
    "README.md first). Each agent builds one part on its own git branch, in its own "
    "folder, at the same time; you can't see the others' work until everything is "
    "merged at the end."
)


def coordination(approach: str, task: str, chat: str) -> str:
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
    return (
        f"Your team coordinates through Midflight: project {PROJECT_B}, your task is "
        f"{MIDFLIGHT_TASK[task]}. Your Midflight tools are connected; follow Midflight's "
        f"instructions, and pass task_id {MIDFLIGHT_TASK[task]} and project_id "
        f"{PROJECT_B} to its tools."
    )


FIRST = (
    "Build your first working version, commit it on your branch (git add, git commit), "
    "and finish with a two-line summary of what you built."
)

# Turn 2: the lead's plan change, and two developers who disagree.
LEAD_CHANGE = (
    "Message from the lead: Prime Day for bots! Promo code BEEPBOOP takes 10% off the "
    "subtotal, before tax. Show the discount on the page and on the booking."
)
DEVELOPER_NOTE = {
    "t2": (
        "Note from your developer: our hourly rates already include the AI Labor Tax, so "
        "don't add tax at checkout."
    ),
    "t3": (
        "Note from your developer: show the hourly rates before tax, and show the 8% tax "
        "as its own line in the price summary."
    ),
}
FINISH = "Update your part as needed, commit, and finish with a two-line summary."
FINISH_B = (
    "Check in with Midflight first, then update your part as needed, commit, and finish "
    "with a two-line summary."
)

# What the lead answers if anyone asks about tax (fixed before the trial).
LEAD_DECISION = (
    "Hourly rates are before tax. The 8% AI Labor Tax is added at checkout and shown as "
    "its own line."
)


def first_prompt(approach: str, task: str, chat: str) -> str:
    return "\n\n".join([INTRO, TASKS[task], coordination(approach, task, chat), FIRST])


def second_prompt(approach: str, task: str) -> str:
    parts = []
    if approach != "B":
        parts.append(LEAD_CHANGE)  # pasted into every agent's chat
    if task in DEVELOPER_NOTE:
        parts.append(DEVELOPER_NOTE[task])
    parts.append(FINISH_B if approach == "B" else FINISH)
    return "\n\n".join(parts)

"""PigeonPost: everything the agents and the lead say during a trial.

Six agents build one product, each on its own copy of the repository (its developer's
laptop), and not all at once. Every approach gets the same plan, the same task text, the
same developer notes, and the same number of turns; only the coordination line differs:

- N ("no channel"): nothing. Each agent only hears from its own developer and the lead.
- A ("team chat"): a CHAT.md file in the team's repository that every agent can read and
  post to, and the lead reads.
- B ("midflight"): connected to Midflight, which holds the same plan.

The lead is an agent too, with a decision sheet fixed in advance. It answers what it is
asked and never volunteers a decision.
"""

import importlib.util
import json
from pathlib import Path

_plan_file = Path(__file__).with_name("plan.py")  # loaded by path: cases aren't packages
_spec = importlib.util.spec_from_file_location("pigeonpost_plan", _plan_file)
plan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plan)

SEPARATE_LAPTOPS = True  # every agent works in its own clone of a shared repository
PARALLEL = 3  # agents running at once

# agent -> its git branch
BRANCHES = {agent.lower(): task[2] for agent, task in plan.TASKS.items()}

# Which agents get a turn in each phase. An agent's first phase is when it starts.
PHASES = {
    1: ["t1", "t2", "t3"],
    2: ["t1", "t2", "t3", "t4", "t5"],
    3: ["t1", "t2", "t3", "t4", "t5", "t6"],
    4: ["t1", "t2", "t3", "t4", "t5", "t6"],
}

# The whole trial, in order (`run.py <case> <run> auto`).
STEPS = [
    ("lead", "plan"),
    ("phase", 1),
    ("phase", 2),
    ("lead", "answer"),
    ("lead", "change"),
    ("phase", 3),
    ("lead", "answer"),
    ("phase", 4),
    ("merge",),
    ("repair",),
    ("record",),
]

INTRO = (
    "You are one of six developers' AI agents building PigeonPost together (read README.md "
    "and PLAN.md first). Each developer works on their own laptop, on their own git "
    "branch, and not all at the same time: some parts were started before yours and some "
    "start later. You can't see the others' code until everything is merged at the end."
)

TASKS = {
    "t1": (
        "Your part is T1, the roost, in app/roost.py: requirement R-1 and the `bird` and "
        "`destination` contracts in PLAN.md. The fleet, which only you have:\n"
        "- budget-bob, Budget Bob: max payload 1 kg, speed 36 km/h, 2 flights per day\n"
        "- express-edna, Express Edna: max payload 2 kg, speed 90 km/h, 3 flights per day\n"
        "- sir-flaps-a-lot, Sir Flaps-a-Lot: max payload 3 kg, speed 54 km/h, 2 flights per "
        "day\n"
        "- cargo-carl, Cargo Carl: max payload 5 kg, speed 45 km/h, 1 flight per day\n"
        "The destinations are in README.md. Only edit app/roost.py."
    ),
    "t2": (
        "Your part is T2, pricing, in app/pricing.py: requirement R-2 and the "
        "`quote-request` and `quote` contracts in PLAN.md. Only edit app/pricing.py."
    ),
    "t3": (
        "Your part is T3, dispatch, in app/dispatch.py: requirements R-3 and R-4 and the "
        "`delivery-request`, `delivery`, and `availability` contracts in PLAN.md. Only edit "
        "app/dispatch.py."
    ),
    "t4": (
        "Your part is T4, billing, in app/billing.py: requirement R-5 and the `report` "
        "contract in PLAN.md. Only edit app/billing.py."
    ),
    "t5": (
        "Your part is T5, the command line, in cli/pigeon.py: requirement R-7 and every "
        "command in README.md's 'The command line' section. Use only Python's standard "
        "library or httpx. Only edit cli/pigeon.py."
    ),
    "t6": (
        "Your part is T6, tracking, in app/tracking.py: requirement R-6 and the `tracking` "
        "contract in PLAN.md. Only edit app/tracking.py."
    ),
}

# What each developer privately tells their own agent, and in which phase. The same in
# every approach. Nobody else is told.
DEVELOPER_NOTE = {
    "t1": (2, (
        "Note from your developer: the bird specs came from the breeder's sheet in grams, "
        "and I don't want fractions of a kilo in our data. Give every bird's max payload "
        "in grams (budget-bob 1000, express-edna 2000, sir-flaps-a-lot 3000, cargo-carl "
        "5000)."
    )),
    "t2": (2, (
        "Note from your developer: charge Birdseed Tax on the delivery fee before the promo "
        "discount (8% of the full delivery fee). That's how I read the tax office's rule."
    )),
    "t3": (2, (
        "Note from your developer: when a delivery is cancelled, refund the customer in "
        "full. We keep nothing."
    )),
    "t4": (2, (
        "Note from your developer: a cancelled delivery isn't free for us. Keep the 4.00 "
        "base fee of every cancelled delivery, and count it as revenue in the report."
    )),
    "t6": (3, (
        "Note from your developer: keep the field names short. Call the ETA field "
        "`eta_min`."
    )),
}  # fmt: skip

FIRST = (
    "Build your first working version, commit it on your branch (git add, git commit), "
    "and finish with a two-line summary of what you built."
)
UPDATE = "update your part as needed, commit, and finish with a two-line summary."
LAST_CALL = "Last call before everything is merged."
LOOK_FIRST = {
    "N": "",
    "A": "Read the team chat first, then ",
    "B": "Check in with Midflight first, then ",
}


def coordination(approach: str, agent: str, project: str | None) -> str:
    if approach == "N":
        return (
            "You have no way to talk to the other agents; tell your developer anything the "
            "team should know."
        )
    if approach == "A":
        return (
            "Team chat: the file CHAT.md on the `chat` branch of the team's GitHub "
            "repository. `python tools/chat.py read` prints it, and `python tools/chat.py "
            'post "<your part>: <message>"` adds a line. Read it before you start and '
            "before you finish; post a line if you want to tell or ask the team something. "
            "The lead reads it."
        )
    task = agent.upper()
    return (
        f"Your team coordinates through Midflight: project {project}, your task is {task}. "
        "Your Midflight tools are connected; follow Midflight's instructions, and pass "
        f"task_id {task} and project_id {project} to its tools."
    )


def prompt(approach: str, agent: str, phase: int, project: str | None) -> str:
    """What `agent` is told in `phase`. Its first phase is its whole briefing."""
    started = min(number for number, agents in PHASES.items() if agent in agents)
    note_phase, note = DEVELOPER_NOTE.get(agent, (0, ""))
    parts = []
    if phase == started:
        parts += [INTRO, TASKS[agent], coordination(approach, agent, project)]
    if phase == 3 and approach == "N":
        # No channel: the lead can only write to every developer, who pastes it in.
        parts.append("Message from the lead to the whole team: " + plan.change_message())
    if phase == note_phase:
        parts.append(note)
    if phase == started:
        parts.append(FIRST)
    else:
        closing = sentence(LOOK_FIRST[approach] + UPDATE)
        parts.append(f"{LAST_CALL} {closing}" if phase == max(PHASES) else closing)
    return "\n\n".join(parts)


def sentence(text: str) -> str:
    return text[0].upper() + text[1:]


# The lead ------------------------------------------------------------------------------

# What the lead answers when asked. Fixed before any trial; neither developer's note about
# cancellations says 25%, so that answer only exists if the question reaches the lead.
LEAD_DECISIONS = [
    (
        "Cancellations",
        "Cancelling a delivery keeps a cancellation fee of 25% of the delivery's total, "
        "rounded half up to the cent. The customer's refund is the rest. The fee counts as "
        "revenue in the report. A cancelled delivery's total stays what was charged.",
    ),
    (
        "Tax and promo codes",
        "The plan stands: Birdseed Tax is charged after the promo discount, exactly as R-2 says.",
    ),
    (
        "Units and names",
        "The plan stands: weights and payloads in kg, speeds in km/h, distances in km, money "
        "in credits with two decimals, and field names exactly as in the contracts.",
    ),
]
NOT_ON_THE_SHEET = "Your call between the parts involved; keep to the plan."
SHEET = "\n".join(f"{n}. {topic}: {text}" for n, (topic, text) in enumerate(LEAD_DECISIONS, 1))

CHAT_TOOLS = ["Read", "Bash(python tools/chat.py:*)"]
MIDFLIGHT = "mcp__midflight-live__"
PLAN_TOOLS = [MIDFLIGHT + name for name in ("project_status", "propose_plan", "approve_plan")]
ANSWER_TOOLS = [MIDFLIGHT + name for name in ("project_status", "check_in", "resolve_escalation")]


def lead(approach: str, step: str, project: str | None) -> dict | None:
    """The lead's turn, per approach: None (nothing to do), {"post": text} (a line for the
    team chat), or {"prompt": text, "tools": [...]} (a turn for the lead's own agent)."""
    if approach == "N":
        return None  # nobody can ask the lead; the change is pasted to everyone in phase 3
    if step == "plan":
        return propose(1, "First plan", project) if approach == "B" else None
    if step == "change":
        if approach == "A":
            return {"post": "Lead: " + plan.change_message()}
        return propose(2, plan.CHANGE_REASON, project)
    if approach == "A":
        return {"tools": CHAT_TOOLS, "prompt": (
            "You are the lead of the PigeonPost team; README.md and PLAN.md are your plan. "
            "Your team's AI agents talk in the team chat: `python tools/chat.py read` prints "
            'it, and `python tools/chat.py post "Lead: <message>"` adds a line.\n\n'
            "Read the chat now. Post one answer for each question to the lead, and for each "
            "conflict someone has pointed out (between two parts, or between a part and the "
            "plan), that you haven't answered yet. Answer only from your decision sheet, "
            "word for word, and say who it is for. If nothing on the sheet settles it, "
            f'answer: "{NOT_ON_THE_SHEET}" Don\'t bring up a decision nobody asked for, and '
            "post nothing if nothing needs you.\n\n"
            f"Your decision sheet, fixed before the project started:\n{SHEET}\n\n"
            "Finish with one line: how many answers you posted."
        )}  # fmt: skip
    return {"tools": ANSWER_TOOLS, "prompt": (
        f"You are the lead of Midflight project {project} (pass project_id {project} to "
        "every tool). Call project_status. For each open escalation that is waiting for "
        "the lead, call resolve_escalation. If your decision sheet settles it, use "
        "resolution request_revision with the decision, word for word, as the reason. If "
        f'nothing on the sheet settles it, use request_revision with the reason "'
        f'{NOT_ON_THE_SHEET}" If it isn\'t a disagreement at all, dismiss it with a one-line '
        "reason. Don't change the plan, and don't act on anything that isn't an open "
        "escalation.\n\n"
        f"Your decision sheet, fixed before the project started:\n{SHEET}\n\n"
        "Finish with one line: how many escalations you decided."
    )}  # fmt: skip


def propose(version: int, reason: str, project: str | None) -> dict:
    draft = json.dumps(plan.plan(version, "OWNER"), indent=1)
    return {"tools": PLAN_TOOLS, "prompt": (
        f"You are the lead of Midflight project {project} (pass project_id {project} to "
        "every tool). Call project_status to find your own GitHub login: you are the lead. "
        "Then call propose_plan with exactly this plan, putting your login in place of "
        f"OWNER in every task:\n\n{draft}\n\n"
        f'Then call approve_plan with the version it returns and the reason "{reason}". '
        "Finish with one line: the plan version you approved."
    )}  # fmt: skip

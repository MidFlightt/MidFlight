# PigeonPost with Midflight: your prompts for Codex

You build three parts of PigeonPost: **T3 Dispatch**, **T5 Command line**, and **T6
Tracking**. Somesh is the lead and builds the other three. Midflight keeps your Codex and
his agent building to the same plan.

Work through this page top to bottom. Every grey box is something to paste: a command
into your terminal, or a prompt into Codex.

You need git, Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and Codex signed
in.

## Set up (once)

**1. Get the code.** Accept the GitHub invite to `MidFlightt/pigeonpost` first; the
repository is private.

```bash
git clone https://github.com/MidFlightt/pigeonpost.git
```

```bash
cd pigeonpost
```

**2. Connect Midflight to Codex.**

```bash
codex mcp add midflight --url https://5hwub7vaxiyz6oezhxrs3qivaa0cvjvy.lambda-url.us-east-1.on.aws/mcp
```

```bash
codex mcp login midflight
```

The second command opens a browser: sign in with GitHub. Then start `codex` in the
`pigeonpost` folder and type `/mcp`. You should see `midflight` with its tools.

**3. Join the project.** Somesh sends you a join code. Paste into Codex, with the code in
place of `MF-XXXX-XXXX`:

```text
Using the midflight tools, join Midflight project MF-XXXX-XXXX, then list my Midflight projects.
```

Tell Somesh your GitHub login. Wait until he says the plan is approved before you go on.

## Build

Do the tasks in this order. Each one is a single prompt.

### Prompt 1: dispatch (T3)

```text
Create and switch to branch t3-dispatch from main. Read README.md and PLAN.md. My Midflight task is T3 in the PigeonPost project. Follow these steps in order:
1. Call the midflight check_in tool for task T3 and read my requirements, my contracts, any directives, and what other tasks assume about mine.
2. Call submit_claim before writing any code. List every contract I provide or consume with exact field names and types. In assumptions, put everything you are taking for granted about other tasks, with units, and name the task each one is about.
3. Wait for the verdict. If it is needs_revision, fix the claim and submit it again. If it is human_review_required, tell me the question and build only the parts it does not touch.
4. Build app/dispatch.py. Edit only that file.
5. Call check_in again before committing, deal with anything new, then commit.
Finish by telling me what is waiting for the lead, if anything.
```

### Prompt 2: the command line (T5)

```text
Create and switch to branch t5-cli from main. Read README.md and PLAN.md. My Midflight task is T5 in the PigeonPost project. Follow these steps in order:
1. Call the midflight check_in tool for task T5 and read my requirements, my contracts, any directives, and what other tasks assume about mine.
2. Call submit_claim before writing any code. List every contract I consume with exact field names and types. In assumptions, put everything you are taking for granted about other tasks, with units, and name the task each one is about.
3. Wait for the verdict. If it is needs_revision, fix the claim and submit it again. If it is human_review_required, tell me the question and build only the parts it does not touch.
4. Build cli/pigeon.py with every command in README.md's "The command line" section. Use only Python's standard library or httpx. Edit only that file.
5. Call check_in again before committing, deal with anything new, then commit.
Finish by telling me what is waiting for the lead, if anything.
```

### Prompt 3: tracking (T6)

```text
Create and switch to branch t6-tracking from main. Read README.md and PLAN.md. My Midflight task is T6 in the PigeonPost project. Follow these steps in order:
1. Call the midflight check_in tool for task T6 and read my requirements, my contracts, any directives, and what other tasks assume about mine.
2. Call submit_claim before writing any code. List every contract I provide or consume with exact field names and types. In assumptions, put everything you are taking for granted about other tasks, with units, and name the task each one is about.
3. Wait for the verdict. If it is needs_revision, fix the claim and submit it again. If it is human_review_required, tell me the question and build only the parts it does not touch.
4. Build app/tracking.py. Edit only that file.
5. Call check_in again before committing, deal with anything new, then commit.
Finish by telling me what is waiting for the lead, if anything.
```

## Keep in step

Midflight can't interrupt Codex. News only arrives when Codex checks in. Paste the
matching prompt whenever you sit down again, and whenever Somesh says the plan changed or
he made a decision.

### Prompt 4: catch up on dispatch (T3)

```text
Switch to branch t3-dispatch. Call the midflight check_in tool for task T3. Answer every directive with acknowledge_directive. If a directive, a decision, or another task's assumption changes my work, submit a revised claim and wait for the verdict before changing code. Then update app/dispatch.py, check in again, and commit. Tell me what changed.
```

### Prompt 5: catch up on the command line (T5)

```text
Switch to branch t5-cli. Call the midflight check_in tool for task T5. Answer every directive with acknowledge_directive. If a directive, a decision, or another task's assumption changes my work, submit a revised claim and wait for the verdict before changing code. Then update cli/pigeon.py, check in again, and commit. Tell me what changed.
```

### Prompt 6: catch up on tracking (T6)

```text
Switch to branch t6-tracking. Call the midflight check_in tool for task T6. Answer every directive with acknowledge_directive. If a directive, a decision, or another task's assumption changes my work, submit a revised claim and wait for the verdict before changing code. Then update app/tracking.py, check in again, and commit. Tell me what changed.
```

### Prompt 7: when Codex is torn between you and the lead

If Codex says the lead decided something that goes against what you told it, and asks
again:

```text
The lead's decision stands. Revise the claim to match it, wait for the verdict, change the code, and commit.
```

## Finish

Run one of these per task when it is done.

### Prompt 8: push dispatch (T3)

```text
Switch to branch t3-dispatch. Call the midflight check_in tool for task T3. If it says ready to push, push the branch and open a pull request into main. If not, tell me exactly what is blocking.
```

### Prompt 9: push the command line (T5)

```text
Switch to branch t5-cli. Call the midflight check_in tool for task T5. If it says ready to push, push the branch and open a pull request into main. If not, tell me exactly what is blocking.
```

### Prompt 10: push tracking (T6)

```text
Switch to branch t6-tracking. Call the midflight check_in tool for task T6. If it says ready to push, push the branch and open a pull request into main. If not, tell me exactly what is blocking.
```

## Four habits that get a good result

- **Claim before code.** The claim is where Midflight catches a mismatch with Somesh's
  parts, before there is code to redo.
- **Say assumptions with units.** "T1's max_payload is in kg." "T2's total includes
  tax."
- **If you want something the plan doesn't say, tell Codex and let it put that in the
  claim.** Don't have it build the change quietly. Midflight either settles it or asks
  Somesh.
- **Check in often.** It is the only way news reaches Codex.

## If something goes wrong

| What you see | What to do |
| --- | --- |
| `/mcp` doesn't list `midflight` | Run `codex mcp list`. If it is missing, repeat step 2. If it is there, run `codex mcp login midflight` again. |
| "You aren't in a project" | Repeat step 3 with the join code. |
| "Task T3 isn't yours" or no task found | The plan isn't approved yet, or it has a different GitHub login for you. Tell Somesh your exact login. |
| The verdict is `human_review_required` | Somesh has to decide. Tell him, and keep building the parts the question doesn't touch. |
| A push is refused | Paste the matching "push" prompt: it tells you what is blocking. |

## Starting over

When Somesh resets the repository, bring your copy back to the starter:

```bash
python reset.py --local
```

It deletes your local branches and anything not committed to `main`. Then ask Codex to
"withdraw my Midflight claims for T3, T5, and T6", and start again at Prompt 1 once
Somesh has approved the plan again.

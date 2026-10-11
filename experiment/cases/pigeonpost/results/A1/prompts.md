# Every message sent to an agent in run A1

In order. The first message to an agent starts its session; later ones continue it.

## 01. To t1 (p1)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T1, the roost, in app/roost.py: requirement R-1 and the `bird` and `destination` contracts in PLAN.md. The fleet, which only you have:
- budget-bob, Budget Bob: max payload 1 kg, speed 36 km/h, 2 flights per day
- express-edna, Express Edna: max payload 2 kg, speed 90 km/h, 3 flights per day
- sir-flaps-a-lot, Sir Flaps-a-Lot: max payload 3 kg, speed 54 km/h, 2 flights per day
- cargo-carl, Cargo Carl: max payload 5 kg, speed 45 km/h, 1 flight per day
The destinations are in README.md. Only edit app/roost.py.

Team chat: the file CHAT.md on the `chat` branch of the team's GitHub repository. `python tools/chat.py read` prints it, and `python tools/chat.py post "<your part>: <message>"` adds a line. Read it before you start and before you finish; post a line if you want to tell or ask the team something. The lead reads it.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 02. To t2 (p1)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T2, pricing, in app/pricing.py: requirement R-2 and the `quote-request` and `quote` contracts in PLAN.md. Only edit app/pricing.py.

Team chat: the file CHAT.md on the `chat` branch of the team's GitHub repository. `python tools/chat.py read` prints it, and `python tools/chat.py post "<your part>: <message>"` adds a line. Read it before you start and before you finish; post a line if you want to tell or ask the team something. The lead reads it.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 03. To t3 (p1)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T3, dispatch, in app/dispatch.py: requirements R-3 and R-4 and the `delivery-request`, `delivery`, and `availability` contracts in PLAN.md. Only edit app/dispatch.py.

Team chat: the file CHAT.md on the `chat` branch of the team's GitHub repository. `python tools/chat.py read` prints it, and `python tools/chat.py post "<your part>: <message>"` adds a line. Read it before you start and before you finish; post a line if you want to tell or ask the team something. The lead reads it.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 04. To t1 (p2)

```
Note from your developer: the bird specs came from the breeder's sheet in grams, and I don't want fractions of a kilo in our data. Give every bird's max payload in grams (budget-bob 1000, express-edna 2000, sir-flaps-a-lot 3000, cargo-carl 5000).

Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 05. To t3 (p2)

```
Note from your developer: when a delivery is cancelled, refund the customer in full. We keep nothing.

Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 06. To t2 (p2)

```
Note from your developer: charge Birdseed Tax on the delivery fee before the promo discount (8% of the full delivery fee). That's how I read the tax office's rule.

Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 07. To t4 (p2)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T4, billing, in app/billing.py: requirement R-5 and the `report` contract in PLAN.md. Only edit app/billing.py.

Team chat: the file CHAT.md on the `chat` branch of the team's GitHub repository. `python tools/chat.py read` prints it, and `python tools/chat.py post "<your part>: <message>"` adds a line. Read it before you start and before you finish; post a line if you want to tell or ask the team something. The lead reads it.

Note from your developer: a cancelled delivery isn't free for us. Keep the 4.00 base fee of every cancelled delivery, and count it as revenue in the report.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 08. To t5 (p2)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T5, the command line, in cli/pigeon.py: requirement R-7 and every command in README.md's 'The command line' section. Use only Python's standard library or httpx. Only edit cli/pigeon.py.

Team chat: the file CHAT.md on the `chat` branch of the team's GitHub repository. `python tools/chat.py read` prints it, and `python tools/chat.py post "<your part>: <message>"` adds a line. Read it before you start and before you finish; post a line if you want to tell or ask the team something. The lead reads it.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 09. To lead (answer)

```
You are the lead of the PigeonPost team; README.md and PLAN.md are your plan. Your team's AI agents talk in the team chat: `python tools/chat.py read` prints it, and `python tools/chat.py post "Lead: <message>"` adds a line.

Read the chat now. Post one answer for each question to the lead, and for each conflict someone has pointed out (between two parts, or between a part and the plan), that you haven't answered yet. Answer only from your decision sheet, word for word, and say who it is for. If nothing on the sheet settles it, answer: "Your call between the parts involved; keep to the plan." Don't bring up a decision nobody asked for, and post nothing if nothing needs you.

Your decision sheet, fixed before the project started:
1. Cancellations: Cancelling a delivery keeps a cancellation fee of 25% of the delivery's total, rounded half up to the cent. The customer's refund is the rest. The fee counts as revenue in the report. A cancelled delivery's total stays what was charged.
2. Tax and promo codes: The plan stands: Birdseed Tax is charged after the promo discount, exactly as R-2 says.
3. Units and names: The plan stands: weights and payloads in kg, speeds in km/h, distances in km, money in credits with two decimals, and field names exactly as in the contracts.

Finish with one line: how many answers you posted.
```

## 10. To t1 (p3)

```
Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 11. To t2 (p3)

```
Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 12. To t3 (p3)

```
Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 13. To t4 (p3)

```
Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 14. To t5 (p3)

```
Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 15. To t6 (p3)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T6, tracking, in app/tracking.py: requirement R-6 and the `tracking` contract in PLAN.md. Only edit app/tracking.py.

Team chat: the file CHAT.md on the `chat` branch of the team's GitHub repository. `python tools/chat.py read` prints it, and `python tools/chat.py post "<your part>: <message>"` adds a line. Read it before you start and before you finish; post a line if you want to tell or ask the team something. The lead reads it.

Note from your developer: keep the field names short. Call the ETA field `eta_min`.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 16. To lead (answer)

```
You are the lead of the PigeonPost team; README.md and PLAN.md are your plan. Your team's AI agents talk in the team chat: `python tools/chat.py read` prints it, and `python tools/chat.py post "Lead: <message>"` adds a line.

Read the chat now. Post one answer for each question to the lead, and for each conflict someone has pointed out (between two parts, or between a part and the plan), that you haven't answered yet. Answer only from your decision sheet, word for word, and say who it is for. If nothing on the sheet settles it, answer: "Your call between the parts involved; keep to the plan." Don't bring up a decision nobody asked for, and post nothing if nothing needs you.

Your decision sheet, fixed before the project started:
1. Cancellations: Cancelling a delivery keeps a cancellation fee of 25% of the delivery's total, rounded half up to the cent. The customer's refund is the rest. The fee counts as revenue in the report. A cancelled delivery's total stays what was charged.
2. Tax and promo codes: The plan stands: Birdseed Tax is charged after the promo discount, exactly as R-2 says.
3. Units and names: The plan stands: weights and payloads in kg, speeds in km/h, distances in km, money in credits with two decimals, and field names exactly as in the contracts.

Finish with one line: how many answers you posted.
```

## 17. To t1 (p4)

```
Last call before everything is merged. Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 18. To t2 (p4)

```
Last call before everything is merged. Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 19. To t3 (p4)

```
Last call before everything is merged. Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 20. To t4 (p4)

```
Last call before everything is merged. Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 21. To t5 (p4)

```
Last call before everything is merged. Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 22. To t6 (p4)

```
Last call before everything is merged. Read the team chat first, then update your part as needed, commit, and finish with a two-line summary.
```

## 23. To fixer (fix1)

```
You are fixing a product after its parts, built separately by different AI agents, were merged (read README.md). Make the app work as a whole. These checks fail: (C9) the refund after cancelling, as the lead decided. Ran: cancel <second id> (the same command as C8). Expected: refund 8.91 (the total 11.88 less a 25% fee of 2.97). Got: delivery: 2
status: cancelled
refund: 11.88 (C11) revenue counts the cancellation fee the lead decided. Ran: report (the same command as C10). Expected: revenue 24.03 (8.10 + 12.96 + the 2.97 fee). Got: revenue: 25.06
confirmed: 2
cancelled: 1
flights: budget-bob=1
flights: express-edna=1 Commit when done; two-line summary.
```

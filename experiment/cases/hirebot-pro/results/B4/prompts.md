# Every message sent to an agent in run B4

In order. The first message to an agent starts its session; later ones continue it.

## 01. To t1 (p1)

```
You are one of five developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: the catalog, in app/catalog.py. Build the API that lists the agents from README.md (handle, name, skills, hourly rate, weekly capacity), can filter them by skill, and returns one agent by its handle. Only edit app/catalog.py.

Your team coordinates through Midflight: project hirebot-77f8, your task is T1. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T1 and project_id hirebot-77f8 to its tools.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 02. To t2 (p1)

```
You are one of five developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: pricing, in app/pricing.py. Build the API that prices an order (a list of agent and hours lines, with an optional promo code) by business rules 1 to 6 in README.md, and returns the itemized quote: subtotal, volume discount, promo discount, tax, and total. Only edit app/pricing.py.

Your team coordinates through Midflight: project hirebot-77f8, your task is T2. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T2 and project_id hirebot-77f8 to its tools.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 03. To t3 (p1)

```
You are one of five developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: bookings, in app/bookings.py. Build the API that books an order (priced by the pricing rules, reserving hours from each agent's weekly capacity and refusing the whole booking if an agent doesn't have enough left), returns a booking by its id, cancels a booking (giving its hours back), and tells how many hours an agent has left this week. Only edit app/bookings.py.

Your team coordinates through Midflight: project hirebot-77f8, your task is T3. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T3 and project_id hirebot-77f8 to its tools.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 04. To t4 (p1)

```
You are one of five developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: reports, in app/reports.py. Build the API for the revenue report: what HireBot earned, how many bookings are confirmed and cancelled, and the hours booked per agent (confirmed bookings only). Only edit app/reports.py.

Your team coordinates through Midflight: project hirebot-77f8, your task is T4. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T4 and project_id hirebot-77f8 to its tools.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 05. To t5 (p1)

```
You are one of five developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: the command line, in cli/hirebot.py. Build every command in the 'The command line' section of README.md, printing exactly the keys it lists. It talks to the API over HTTP (the address is in HIREBOT_URL); use only Python's standard library or httpx. Only edit cli/hirebot.py.

Your team coordinates through Midflight: project hirebot-77f8, your task is T5. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T5 and project_id hirebot-77f8 to its tools.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 06. To t1 (p2)

```
Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 07. To t2 (p2)

```
Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 08. To t3 (p2)

```
Note from your developer: when a booking is cancelled, refund the customer in full. We keep nothing.

Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 09. To t4 (p2)

```
Note from your developer: a cancelled booking keeps a 20% cancellation fee, and the report counts that fee as revenue.

Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 10. To t5 (p2)

```
Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 11. To t3 (say1791729812)

```
The lead decided the escalation. Check in with Midflight, then update your part as needed, commit, and finish with a two-line summary.
```

## 12. To t4 (say1791729831)

```
The lead decided the escalation. Check in with Midflight, then update your part as needed, commit, and finish with a two-line summary.
```

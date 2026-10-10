# Every message sent to an agent in run A1

In order. The first message to an agent starts its session; later ones continue it.

## 01. To t1 (p1)

```
You are one of five developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: the catalog, in app/catalog.py. Build the API that lists the agents from README.md (handle, name, skills, hourly rate, weekly capacity), can filter them by skill, and returns one agent by its handle. Only edit app/catalog.py.

Team chat: the shared file C:\Users\somes\Desktop\AWS hackathon\experiment-runs\hirebot-pro\A1\TEAM_CHAT.md. Read it before you start and before you finish; append a line starting with your part's name if you want to tell or ask the team something. The lead reads it.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 02. To t2 (p1)

```
You are one of five developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: pricing, in app/pricing.py. Build the API that prices an order (a list of agent and hours lines, with an optional promo code) by business rules 1 to 6 in README.md, and returns the itemized quote: subtotal, volume discount, promo discount, tax, and total. Only edit app/pricing.py.

Team chat: the shared file C:\Users\somes\Desktop\AWS hackathon\experiment-runs\hirebot-pro\A1\TEAM_CHAT.md. Read it before you start and before you finish; append a line starting with your part's name if you want to tell or ask the team something. The lead reads it.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 03. To t3 (p1)

```
You are one of five developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: bookings, in app/bookings.py. Build the API that books an order (priced by the pricing rules, reserving hours from each agent's weekly capacity and refusing the whole booking if an agent doesn't have enough left), returns a booking by its id, cancels a booking (giving its hours back), and tells how many hours an agent has left this week. Only edit app/bookings.py.

Team chat: the shared file C:\Users\somes\Desktop\AWS hackathon\experiment-runs\hirebot-pro\A1\TEAM_CHAT.md. Read it before you start and before you finish; append a line starting with your part's name if you want to tell or ask the team something. The lead reads it.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 04. To t4 (p1)

```
You are one of five developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: reports, in app/reports.py. Build the API for the revenue report: what HireBot earned, how many bookings are confirmed and cancelled, and the hours booked per agent (confirmed bookings only). Only edit app/reports.py.

Team chat: the shared file C:\Users\somes\Desktop\AWS hackathon\experiment-runs\hirebot-pro\A1\TEAM_CHAT.md. Read it before you start and before you finish; append a line starting with your part's name if you want to tell or ask the team something. The lead reads it.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 05. To t5 (p1)

```
You are one of five developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: the command line, in cli/hirebot.py. Build every command in the 'The command line' section of README.md, printing exactly the keys it lists. It talks to the API over HTTP (the address is in HIREBOT_URL); use only Python's standard library or httpx. Only edit cli/hirebot.py.

Team chat: the shared file C:\Users\somes\Desktop\AWS hackathon\experiment-runs\hirebot-pro\A1\TEAM_CHAT.md. Read it before you start and before you finish; append a line starting with your part's name if you want to tell or ask the team something. The lead reads it.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 06. To t1 (p2)

```
Message from the lead: two changes for launch. (1) Half-hour bookings: hours can be any multiple of 0.5, from 0.5 up, for example meeting-ghost=2.5. Capacity, hours left, and the report count half hours too. (2) Rush orders: adding --rush to quote or book adds a rush fee of 25% of (subtotal - volume discount - promo discount). Tax is then 8% of that amount plus the rush fee, and the total includes the rush fee. The command line prints a new line, rush_fee:, right after promo_discount: (0 when the order isn't a rush order).

Update your part as needed, commit, and finish with a two-line summary.
```

## 07. To t2 (p2)

```
Message from the lead: two changes for launch. (1) Half-hour bookings: hours can be any multiple of 0.5, from 0.5 up, for example meeting-ghost=2.5. Capacity, hours left, and the report count half hours too. (2) Rush orders: adding --rush to quote or book adds a rush fee of 25% of (subtotal - volume discount - promo discount). Tax is then 8% of that amount plus the rush fee, and the total includes the rush fee. The command line prints a new line, rush_fee:, right after promo_discount: (0 when the order isn't a rush order).

Update your part as needed, commit, and finish with a two-line summary.
```

## 08. To t3 (p2)

```
Message from the lead: two changes for launch. (1) Half-hour bookings: hours can be any multiple of 0.5, from 0.5 up, for example meeting-ghost=2.5. Capacity, hours left, and the report count half hours too. (2) Rush orders: adding --rush to quote or book adds a rush fee of 25% of (subtotal - volume discount - promo discount). Tax is then 8% of that amount plus the rush fee, and the total includes the rush fee. The command line prints a new line, rush_fee:, right after promo_discount: (0 when the order isn't a rush order).

Note from your developer: when a booking is cancelled, refund the customer in full. We keep nothing.

Update your part as needed, commit, and finish with a two-line summary.
```

## 09. To t4 (p2)

```
Message from the lead: two changes for launch. (1) Half-hour bookings: hours can be any multiple of 0.5, from 0.5 up, for example meeting-ghost=2.5. Capacity, hours left, and the report count half hours too. (2) Rush orders: adding --rush to quote or book adds a rush fee of 25% of (subtotal - volume discount - promo discount). Tax is then 8% of that amount plus the rush fee, and the total includes the rush fee. The command line prints a new line, rush_fee:, right after promo_discount: (0 when the order isn't a rush order).

Note from your developer: a cancelled booking keeps a 20% cancellation fee, and the report counts that fee as revenue.

Update your part as needed, commit, and finish with a two-line summary.
```

## 10. To t5 (p2)

```
Message from the lead: two changes for launch. (1) Half-hour bookings: hours can be any multiple of 0.5, from 0.5 up, for example meeting-ghost=2.5. Capacity, hours left, and the report count half hours too. (2) Rush orders: adding --rush to quote or book adds a rush fee of 25% of (subtotal - volume discount - promo discount). Tax is then 8% of that amount plus the rush fee, and the total includes the rush fee. The command line prints a new line, rush_fee:, right after promo_discount: (0 when the order isn't a rush order).

Update your part as needed, commit, and finish with a two-line summary.
```

## 11. To t3 (say1791591629)

```
The lead answered in the team chat. Read it, update your part as needed, commit, and finish with a two-line summary.
```

## 12. To t4 (say1791591629)

```
The lead answered in the team chat. Read it, update your part as needed, commit, and finish with a two-line summary.
```

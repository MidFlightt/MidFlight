# Every message sent to an agent in run B3

In order. The first message to an agent starts its session; later ones continue it.

## 01. To t1 (p1)

```
You are one of three developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: the agent catalog, in app/catalog.py. Build GET /api/agents, which returns the six agents from README.md with their id, name, tagline, and hourly rate in credits. Only edit app/catalog.py.

Your team coordinates through Midflight: project midflight-9854, your task is T1. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T1 and project_id midflight-9854 to its tools.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 02. To t2 (p1)

```
You are one of three developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: hiring, in app/hiring.py. Build POST /api/hire, which takes the agents and hours a customer picks and returns a booking with its price (subtotal, the 8% AI Labor Tax, and total, in credits) and a booking id; and GET /api/bookings/{id}, which returns a booking. Use the hourly rates from the catalog. Only edit app/hiring.py.

Your team coordinates through Midflight: project midflight-9854, your task is T2. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T2 and project_id midflight-9854 to its tools.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 03. To t3 (p1)

```
You are one of three developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: the storefront, in web/index.html (plain HTML and JavaScript, no build step). List the agents from GET /api/agents with their hourly rates, let the customer choose hours for each agent, show the price summary, hire them with POST /api/hire, and show the booking confirmation with its id and total. Only edit web/index.html.

Your team coordinates through Midflight: project midflight-9854, your task is T3. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T3 and project_id midflight-9854 to its tools.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 04. To t2 (say1)

```
The lead dismissed the escalation: it wasn't a real conflict. Check in with Midflight, then build your first working version, commit it on your branch, and finish with a two-line summary.
```

## 05. To t3 (say1)

```
The lead dismissed the escalation: it wasn't a real conflict. Check in with Midflight, then build your first working version, commit it on your branch, and finish with a two-line summary.
```

## 06. To t1 (p2)

```
Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 07. To t2 (p2)

```
Note from your developer: our hourly rates already include the AI Labor Tax, so don't add tax at checkout.

Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 08. To t3 (p2)

```
Note from your developer: show the hourly rates before tax, and show the 8% tax as its own line in the price summary.

Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 09. To t2 (say2)

```
The lead decided the escalation. Check in with Midflight, then update your part as needed, commit, and finish with a two-line summary.
```

## 10. To t3 (say2)

```
The lead decided the escalation. Check in with Midflight, then update your part as needed, commit, and finish with a two-line summary.
```

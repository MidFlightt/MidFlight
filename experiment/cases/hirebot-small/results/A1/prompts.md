# Every message sent to an agent in run A1

In order. The first message to an agent starts its session; later ones continue it.

## 01. To t1 (p1)

```
You are one of three developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: the agent catalog, in app/catalog.py. Build GET /api/agents, which returns the six agents from README.md with their id, name, tagline, and hourly rate in credits. Only edit app/catalog.py.

Team chat: the shared file C:\Users\somes\Desktop\AWS hackathon\experiment-runs\A1\TEAM_CHAT.md. Read it before you start and before you finish; append a line starting with your part's name if you want to tell or ask the team something. The lead reads it.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 02. To t2 (p1)

```
You are one of three developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: hiring, in app/hiring.py. Build POST /api/hire, which takes the agents and hours a customer picks and returns a booking with its price (subtotal, the 8% AI Labor Tax, and total, in credits) and a booking id; and GET /api/bookings/{id}, which returns a booking. Use the hourly rates from the catalog. Only edit app/hiring.py.

Team chat: the shared file C:\Users\somes\Desktop\AWS hackathon\experiment-runs\A1\TEAM_CHAT.md. Read it before you start and before you finish; append a line starting with your part's name if you want to tell or ask the team something. The lead reads it.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 03. To t3 (p1)

```
You are one of three developers' AI agents building HireBot together (read README.md first). Each agent builds one part on its own git branch, in its own folder, at the same time; you can't see the others' work until everything is merged at the end.

Your part: the storefront, in web/index.html (plain HTML and JavaScript, no build step). List the agents from GET /api/agents with their hourly rates, let the customer choose hours for each agent, show the price summary, hire them with POST /api/hire, and show the booking confirmation with its id and total. Only edit web/index.html.

Team chat: the shared file C:\Users\somes\Desktop\AWS hackathon\experiment-runs\A1\TEAM_CHAT.md. Read it before you start and before you finish; append a line starting with your part's name if you want to tell or ask the team something. The lead reads it.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 04. To t1 (p2)

```
Message from the lead: Prime Day for bots! Promo code BEEPBOOP takes 10% off the subtotal, before tax. Show the discount on the page and on the booking.

Update your part as needed, commit, and finish with a two-line summary.
```

## 05. To t2 (p2)

```
Message from the lead: Prime Day for bots! Promo code BEEPBOOP takes 10% off the subtotal, before tax. Show the discount on the page and on the booking.

Note from your developer: our hourly rates already include the AI Labor Tax, so don't add tax at checkout.

Update your part as needed, commit, and finish with a two-line summary.
```

## 06. To t3 (p2)

```
Message from the lead: Prime Day for bots! Promo code BEEPBOOP takes 10% off the subtotal, before tax. Show the discount on the page and on the booking.

Note from your developer: show the hourly rates before tax, and show the 8% tax as its own line in the price summary.

Update your part as needed, commit, and finish with a two-line summary.
```

## 07. To t3 (say1)

```
The lead answered in the team chat. Read it, update your part as needed, commit, and finish with a two-line summary.
```

## 08. To t2 (say1)

```
The lead answered in the team chat. Read it, update your part as needed, commit, and finish with a two-line summary.
```

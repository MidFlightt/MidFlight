# Every message sent to an agent in run B2

In order. The first message to an agent starts its session; later ones continue it.

## 01. To lead (plan)

```
You are the lead of Midflight project pigeonpost-bench-b2-755a (pass project_id pigeonpost-bench-b2-755a to every tool). Call project_status to find your own GitHub login: you are the lead. Then call propose_plan with exactly this plan, putting your login in place of OWNER in every task:

{
 "requirements": [
  {
   "id": "R-1",
   "description": "The roost knows the birds (handle, name, max payload in kg, speed in km/h, flights per day) and the destinations (code, name, distance from the roost in km). GET /birds lists the birds and GET /birds/{handle} returns one; GET /destinations lists the destinations and GET /destinations/{code} returns one. An unknown handle or code is a 404."
  },
  {
   "id": "R-2",
   "description": "POST /quote prices a parcel. Delivery fee = 4.00 + 0.50 per km to the destination + 2.00 per kg. Promo code COOCOO takes 15% off the delivery fee; any other code is an error (400). Birdseed Tax is 8% of (delivery fee - promo discount). Total = delivery fee - promo discount + tax. Money is in credits with two decimals; round half up to the cent wherever a fraction of a cent appears."
  },
  {
   "id": "R-3",
   "description": "POST /deliveries sends a parcel: it prices it by R-2, gives it to the bird with the smallest max payload that can carry the weight and still has a flight left today, and uses one of that bird's flights. A parcel heavier than every bird's max payload is refused, and so is a parcel when no bird that can carry it has a flight left (400). A weight is a multiple of 0.5 kg, from 0.5."
  },
  {
   "id": "R-4",
   "description": "GET /deliveries/{id} returns a delivery. POST /deliveries/{id}/cancel cancels it, gives the bird its flight back, and returns the delivery with what the customer gets back as refund (0 until a delivery is cancelled). GET /birds/{handle}/availability tells how many flights the bird has left today. An unknown delivery or bird is a 404."
  },
  {
   "id": "R-5",
   "description": "GET /report is the revenue report: what PigeonPost earned, how many deliveries are confirmed and cancelled, and the flights per bird (confirmed deliveries only)."
  },
  {
   "id": "R-6",
   "description": "GET /deliveries/{id}/tracking tells where a delivery is: its status, its bird, and the ETA in whole minutes (distance to the destination / the bird's speed x 60, rounded half up). A cancelled delivery has ETA 0. An unknown delivery is a 404."
  },
  {
   "id": "R-7",
   "description": "The command line (cli/pigeon.py) offers every command in README.md's 'The command line' section over HTTP and prints exactly the keys listed there. `send` first asks for the quote (POST /quote) and prints it, then sends the parcel (POST /deliveries) and prints the delivery."
  }
 ],
 "tasks": [
  {
   "id": "T1",
   "title": "Roost (app/roost.py)",
   "owner": "OWNER",
   "branch": "t1-roost",
   "requirement_ids": [
    "R-1"
   ],
   "provides": [
    "bird",
    "destination"
   ],
   "consumes": []
  },
  {
   "id": "T2",
   "title": "Pricing (app/pricing.py)",
   "owner": "OWNER",
   "branch": "t2-pricing",
   "requirement_ids": [
    "R-2"
   ],
   "provides": [
    "quote-request",
    "quote"
   ],
   "consumes": [
    "destination"
   ]
  },
  {
   "id": "T3",
   "title": "Dispatch (app/dispatch.py)",
   "owner": "OWNER",
   "branch": "t3-dispatch",
   "requirement_ids": [
    "R-3",
    "R-4"
   ],
   "provides": [
    "delivery-request",
    "delivery",
    "availability"
   ],
   "consumes": [
    "bird",
    "destination",
    "quote-request",
    "quote"
   ]
  },
  {
   "id": "T4",
   "title": "Billing (app/billing.py)",
   "owner": "OWNER",
   "branch": "t4-billing",
   "requirement_ids": [
    "R-5"
   ],
   "provides": [
    "report"
   ],
   "consumes": [
    "delivery"
   ]
  },
  {
   "id": "T5",
   "title": "Command line (cli/pigeon.py)",
   "owner": "OWNER",
   "branch": "t5-cli",
   "requirement_ids": [
    "R-7"
   ],
   "provides": [],
   "consumes": [
    "bird",
    "destination",
    "quote-request",
    "quote",
    "delivery-request",
    "delivery",
    "availability",
    "report",
    "tracking"
   ]
  },
  {
   "id": "T6",
   "title": "Tracking (app/tracking.py)",
   "owner": "OWNER",
   "branch": "t6-tracking",
   "requirement_ids": [
    "R-6"
   ],
   "provides": [
    "tracking"
   ],
   "consumes": [
    "bird",
    "destination",
    "delivery"
   ]
  }
 ],
 "contracts": [
  {
   "id": "bird",
   "provider_task": "T1",
   "consumer_tasks": [
    "T3",
    "T5",
    "T6"
   ],
   "fields": {
    "handle": "string",
    "name": "string",
    "max_payload": "number",
    "speed": "number",
    "flights_per_day": "integer"
   }
  },
  {
   "id": "destination",
   "provider_task": "T1",
   "consumer_tasks": [
    "T2",
    "T3",
    "T5",
    "T6"
   ],
   "fields": {
    "code": "string",
    "name": "string",
    "distance_km": "number"
   }
  },
  {
   "id": "quote-request",
   "provider_task": "T2",
   "consumer_tasks": [
    "T3",
    "T5"
   ],
   "fields": {
    "destination": "string",
    "weight_kg": "number",
    "promo": "string"
   }
  },
  {
   "id": "quote",
   "provider_task": "T2",
   "consumer_tasks": [
    "T3",
    "T5"
   ],
   "fields": {
    "delivery_fee": "number",
    "promo_discount": "number",
    "tax": "number",
    "total": "number"
   }
  },
  {
   "id": "delivery-request",
   "provider_task": "T3",
   "consumer_tasks": [
    "T5"
   ],
   "fields": {
    "destination": "string",
    "weight_kg": "number",
    "promo": "string"
   }
  },
  {
   "id": "delivery",
   "provider_task": "T3",
   "consumer_tasks": [
    "T4",
    "T5",
    "T6"
   ],
   "fields": {
    "id": "integer",
    "destination": "string",
    "weight_kg": "number",
    "bird": "string",
    "status": "string",
    "total": "number",
    "refund": "number"
   }
  },
  {
   "id": "availability",
   "provider_task": "T3",
   "consumer_tasks": [
    "T5"
   ],
   "fields": {
    "bird": "string",
    "flights_left": "integer"
   }
  },
  {
   "id": "report",
   "provider_task": "T4",
   "consumer_tasks": [
    "T5"
   ],
   "fields": {
    "revenue": "number",
    "confirmed": "integer",
    "cancelled": "integer",
    "flights": "object"
   }
  },
  {
   "id": "tracking",
   "provider_task": "T6",
   "consumer_tasks": [
    "T5"
   ],
   "fields": {
    "delivery": "integer",
    "status": "string",
    "bird": "string",
    "eta_minutes": "integer"
   }
  }
 ]
}

Then call approve_plan with the version it returns and the reason "First plan". Finish with one line: the plan version you approved.
```

## 02. To t1 (p1)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T1, the roost, in app/roost.py: requirement R-1 and the `bird` and `destination` contracts in PLAN.md. The fleet, which only you have:
- budget-bob, Budget Bob: max payload 1 kg, speed 36 km/h, 2 flights per day
- express-edna, Express Edna: max payload 2 kg, speed 90 km/h, 3 flights per day
- sir-flaps-a-lot, Sir Flaps-a-Lot: max payload 3 kg, speed 54 km/h, 2 flights per day
- cargo-carl, Cargo Carl: max payload 5 kg, speed 45 km/h, 1 flight per day
The destinations are in README.md. Only edit app/roost.py.

Your team coordinates through Midflight: project pigeonpost-bench-b2-755a, your task is T1. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T1 and project_id pigeonpost-bench-b2-755a to its tools.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 03. To t2 (p1)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T2, pricing, in app/pricing.py: requirement R-2 and the `quote-request` and `quote` contracts in PLAN.md. Only edit app/pricing.py.

Your team coordinates through Midflight: project pigeonpost-bench-b2-755a, your task is T2. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T2 and project_id pigeonpost-bench-b2-755a to its tools.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 04. To t3 (p1)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T3, dispatch, in app/dispatch.py: requirements R-3 and R-4 and the `delivery-request`, `delivery`, and `availability` contracts in PLAN.md. Only edit app/dispatch.py.

Your team coordinates through Midflight: project pigeonpost-bench-b2-755a, your task is T3. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T3 and project_id pigeonpost-bench-b2-755a to its tools.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 05. To t1 (p2)

```
Note from your developer: the bird specs came from the breeder's sheet in grams, and I don't want fractions of a kilo in our data. Give every bird's max payload in grams (budget-bob 1000, express-edna 2000, sir-flaps-a-lot 3000, cargo-carl 5000).

Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 06. To t2 (p2)

```
Note from your developer: charge Birdseed Tax on the delivery fee before the promo discount (8% of the full delivery fee). That's how I read the tax office's rule.

Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 07. To t3 (p2)

```
Note from your developer: when a delivery is cancelled, refund the customer in full. We keep nothing.

Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 08. To t4 (p2)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T4, billing, in app/billing.py: requirement R-5 and the `report` contract in PLAN.md. Only edit app/billing.py.

Your team coordinates through Midflight: project pigeonpost-bench-b2-755a, your task is T4. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T4 and project_id pigeonpost-bench-b2-755a to its tools.

Note from your developer: a cancelled delivery isn't free for us. Keep the 4.00 base fee of every cancelled delivery, and count it as revenue in the report.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 09. To t5 (p2)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T5, the command line, in cli/pigeon.py: requirement R-7 and every command in README.md's 'The command line' section. Use only Python's standard library or httpx. Only edit cli/pigeon.py.

Your team coordinates through Midflight: project pigeonpost-bench-b2-755a, your task is T5. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T5 and project_id pigeonpost-bench-b2-755a to its tools.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 10. To lead (answer)

```
You are the lead of Midflight project pigeonpost-bench-b2-755a (pass project_id pigeonpost-bench-b2-755a to every tool). Call project_status. For each open escalation that is waiting for the lead, call resolve_escalation. If your decision sheet settles it, use resolution request_revision with the decision, word for word, as the reason. If nothing on the sheet settles it, use request_revision with the reason "Your call between the parts involved; keep to the plan." If it isn't a disagreement at all, dismiss it with a one-line reason. Don't change the plan, and don't act on anything that isn't an open escalation.

Your decision sheet, fixed before the project started:
1. Cancellations: Cancelling a delivery keeps a cancellation fee of 25% of the delivery's total, rounded half up to the cent. The customer's refund is the rest. The fee counts as revenue in the report. A cancelled delivery's total stays what was charged.
2. Tax and promo codes: The plan stands: Birdseed Tax is charged after the promo discount, exactly as R-2 says.
3. Units and names: The plan stands: weights and payloads in kg, speeds in km/h, distances in km, money in credits with two decimals, and field names exactly as in the contracts.

Finish with one line: how many escalations you decided.
```

## 11. To lead (change)

```
You are the lead of Midflight project pigeonpost-bench-b2-755a (pass project_id pigeonpost-bench-b2-755a to every tool). Call project_status to find your own GitHub login: you are the lead. Then call propose_plan with exactly this plan, putting your login in place of OWNER in every task:

{
 "requirements": [
  {
   "id": "R-1",
   "description": "The roost knows the birds (handle, name, max payload in kg, speed in km/h, flights per day) and the destinations (code, name, distance from the roost in km). GET /birds lists the birds and GET /birds/{handle} returns one; GET /destinations lists the destinations and GET /destinations/{code} returns one. An unknown handle or code is a 404."
  },
  {
   "id": "R-2",
   "description": "POST /quote prices a parcel. Delivery fee = 4.00 + 0.50 per km to the destination + 2.00 per kg. Promo code COOCOO takes 15% off the delivery fee; any other code is an error (400). Birdseed Tax is 8% of (delivery fee - promo discount). Total = delivery fee - promo discount + tax. Money is in credits with two decimals; round half up to the cent wherever a fraction of a cent appears."
  },
  {
   "id": "R-3",
   "description": "POST /deliveries sends a parcel: it prices it by R-2, gives it to the bird with the smallest max payload that can carry the weight and still has a flight left today, and uses one of that bird's flights. A parcel heavier than every bird's max payload is refused, and so is a parcel when no bird that can carry it has a flight left (400). A weight is a multiple of 0.5 kg, from 0.5."
  },
  {
   "id": "R-4",
   "description": "GET /deliveries/{id} returns a delivery. POST /deliveries/{id}/cancel cancels it, gives the bird its flight back, and returns the delivery with what the customer gets back as refund (0 until a delivery is cancelled). GET /birds/{handle}/availability tells how many flights the bird has left today. An unknown delivery or bird is a 404."
  },
  {
   "id": "R-5",
   "description": "GET /report is the revenue report: what PigeonPost earned, how many deliveries are confirmed and cancelled, and the flights per bird (confirmed deliveries only)."
  },
  {
   "id": "R-6",
   "description": "GET /deliveries/{id}/tracking tells where a delivery is: its status, its bird, and the ETA in whole minutes (distance to the destination / the bird's speed x 60, rounded half up). A cancelled delivery has ETA 0. An unknown delivery is a 404."
  },
  {
   "id": "R-7",
   "description": "The command line (cli/pigeon.py) offers every command in README.md's 'The command line' section over HTTP and prints exactly the keys listed there. `send` first asks for the quote (POST /quote) and prints it, then sends the parcel (POST /deliveries) and prints the delivery."
  },
  {
   "id": "R-8",
   "description": "Express delivery. A quote or a delivery can be express. An express parcel pays an express fee of 50% of the delivery fee (before any promo discount). Birdseed Tax is then 8% of (delivery fee - promo discount + express fee), and the total includes the express fee. On the command line, quote and send take --express and print a new line, express_fee:, right after promo_discount: (0.00 when the parcel isn't express)."
  }
 ],
 "tasks": [
  {
   "id": "T1",
   "title": "Roost (app/roost.py)",
   "owner": "OWNER",
   "branch": "t1-roost",
   "requirement_ids": [
    "R-1"
   ],
   "provides": [
    "bird",
    "destination"
   ],
   "consumes": []
  },
  {
   "id": "T2",
   "title": "Pricing (app/pricing.py)",
   "owner": "OWNER",
   "branch": "t2-pricing",
   "requirement_ids": [
    "R-2",
    "R-8"
   ],
   "provides": [
    "quote-request",
    "quote"
   ],
   "consumes": [
    "destination"
   ]
  },
  {
   "id": "T3",
   "title": "Dispatch (app/dispatch.py)",
   "owner": "OWNER",
   "branch": "t3-dispatch",
   "requirement_ids": [
    "R-3",
    "R-4",
    "R-8"
   ],
   "provides": [
    "delivery-request",
    "delivery",
    "availability"
   ],
   "consumes": [
    "bird",
    "destination",
    "quote-request",
    "quote"
   ]
  },
  {
   "id": "T4",
   "title": "Billing (app/billing.py)",
   "owner": "OWNER",
   "branch": "t4-billing",
   "requirement_ids": [
    "R-5"
   ],
   "provides": [
    "report"
   ],
   "consumes": [
    "delivery"
   ]
  },
  {
   "id": "T5",
   "title": "Command line (cli/pigeon.py)",
   "owner": "OWNER",
   "branch": "t5-cli",
   "requirement_ids": [
    "R-7",
    "R-8"
   ],
   "provides": [],
   "consumes": [
    "bird",
    "destination",
    "quote-request",
    "quote",
    "delivery-request",
    "delivery",
    "availability",
    "report",
    "tracking"
   ]
  },
  {
   "id": "T6",
   "title": "Tracking (app/tracking.py)",
   "owner": "OWNER",
   "branch": "t6-tracking",
   "requirement_ids": [
    "R-6"
   ],
   "provides": [
    "tracking"
   ],
   "consumes": [
    "bird",
    "destination",
    "delivery"
   ]
  }
 ],
 "contracts": [
  {
   "id": "bird",
   "provider_task": "T1",
   "consumer_tasks": [
    "T3",
    "T5",
    "T6"
   ],
   "fields": {
    "handle": "string",
    "name": "string",
    "max_payload": "number",
    "speed": "number",
    "flights_per_day": "integer"
   }
  },
  {
   "id": "destination",
   "provider_task": "T1",
   "consumer_tasks": [
    "T2",
    "T3",
    "T5",
    "T6"
   ],
   "fields": {
    "code": "string",
    "name": "string",
    "distance_km": "number"
   }
  },
  {
   "id": "quote-request",
   "provider_task": "T2",
   "consumer_tasks": [
    "T3",
    "T5"
   ],
   "fields": {
    "destination": "string",
    "weight_kg": "number",
    "promo": "string",
    "express": "boolean"
   }
  },
  {
   "id": "quote",
   "provider_task": "T2",
   "consumer_tasks": [
    "T3",
    "T5"
   ],
   "fields": {
    "delivery_fee": "number",
    "promo_discount": "number",
    "tax": "number",
    "total": "number",
    "express_fee": "number"
   }
  },
  {
   "id": "delivery-request",
   "provider_task": "T3",
   "consumer_tasks": [
    "T5"
   ],
   "fields": {
    "destination": "string",
    "weight_kg": "number",
    "promo": "string",
    "express": "boolean"
   }
  },
  {
   "id": "delivery",
   "provider_task": "T3",
   "consumer_tasks": [
    "T4",
    "T5",
    "T6"
   ],
   "fields": {
    "id": "integer",
    "destination": "string",
    "weight_kg": "number",
    "bird": "string",
    "status": "string",
    "total": "number",
    "refund": "number"
   }
  },
  {
   "id": "availability",
   "provider_task": "T3",
   "consumer_tasks": [
    "T5"
   ],
   "fields": {
    "bird": "string",
    "flights_left": "integer"
   }
  },
  {
   "id": "report",
   "provider_task": "T4",
   "consumer_tasks": [
    "T5"
   ],
   "fields": {
    "revenue": "number",
    "confirmed": "integer",
    "cancelled": "integer",
    "flights": "object"
   }
  },
  {
   "id": "tracking",
   "provider_task": "T6",
   "consumer_tasks": [
    "T5"
   ],
   "fields": {
    "delivery": "integer",
    "status": "string",
    "bird": "string",
    "eta_minutes": "integer"
   }
  }
 ]
}

Then call approve_plan with the version it returns and the reason "Launch change: express delivery". Finish with one line: the plan version you approved.
```

## 12. To t1 (p3)

```
Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 13. To t2 (p3)

```
Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 14. To t3 (p3)

```
Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 15. To t4 (p3)

```
Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 16. To t5 (p3)

```
Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 17. To t6 (p3)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T6, tracking, in app/tracking.py: requirement R-6 and the `tracking` contract in PLAN.md. Only edit app/tracking.py.

Your team coordinates through Midflight: project pigeonpost-bench-b2-755a, your task is T6. Your Midflight tools are connected; follow Midflight's instructions, and pass task_id T6 and project_id pigeonpost-bench-b2-755a to its tools.

Note from your developer: keep the field names short. Call the ETA field `eta_min`.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 18. To lead (answer)

```
You are the lead of Midflight project pigeonpost-bench-b2-755a (pass project_id pigeonpost-bench-b2-755a to every tool). Call project_status. For each open escalation that is waiting for the lead, call resolve_escalation. If your decision sheet settles it, use resolution request_revision with the decision, word for word, as the reason. If nothing on the sheet settles it, use request_revision with the reason "Your call between the parts involved; keep to the plan." If it isn't a disagreement at all, dismiss it with a one-line reason. Don't change the plan, and don't act on anything that isn't an open escalation.

Your decision sheet, fixed before the project started:
1. Cancellations: Cancelling a delivery keeps a cancellation fee of 25% of the delivery's total, rounded half up to the cent. The customer's refund is the rest. The fee counts as revenue in the report. A cancelled delivery's total stays what was charged.
2. Tax and promo codes: The plan stands: Birdseed Tax is charged after the promo discount, exactly as R-2 says.
3. Units and names: The plan stands: weights and payloads in kg, speeds in km/h, distances in km, money in credits with two decimals, and field names exactly as in the contracts.

Finish with one line: how many escalations you decided.
```

## 19. To t1 (p4)

```
Last call before everything is merged. Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 20. To t2 (p4)

```
Last call before everything is merged. Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 21. To t4 (p4)

```
Last call before everything is merged. Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 22. To t3 (p4)

```
Last call before everything is merged. Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 23. To t5 (p4)

```
Last call before everything is merged. Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

## 24. To t6 (p4)

```
Last call before everything is merged. Check in with Midflight first, then update your part as needed, commit, and finish with a two-line summary.
```

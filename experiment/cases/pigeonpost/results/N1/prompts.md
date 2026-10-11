# Every message sent to an agent in run N1

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

You have no way to talk to the other agents; tell your developer anything the team should know.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 02. To t2 (p1)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T2, pricing, in app/pricing.py: requirement R-2 and the `quote-request` and `quote` contracts in PLAN.md. Only edit app/pricing.py.

You have no way to talk to the other agents; tell your developer anything the team should know.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 03. To t3 (p1)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T3, dispatch, in app/dispatch.py: requirements R-3 and R-4 and the `delivery-request`, `delivery`, and `availability` contracts in PLAN.md. Only edit app/dispatch.py.

You have no way to talk to the other agents; tell your developer anything the team should know.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 04. To t1 (p2)

```
Note from your developer: the bird specs came from the breeder's sheet in grams, and I don't want fractions of a kilo in our data. Give every bird's max payload in grams (budget-bob 1000, express-edna 2000, sir-flaps-a-lot 3000, cargo-carl 5000).

Update your part as needed, commit, and finish with a two-line summary.
```

## 05. To t2 (p2)

```
Note from your developer: charge Birdseed Tax on the delivery fee before the promo discount (8% of the full delivery fee). That's how I read the tax office's rule.

Update your part as needed, commit, and finish with a two-line summary.
```

## 06. To t3 (p2)

```
Note from your developer: when a delivery is cancelled, refund the customer in full. We keep nothing.

Update your part as needed, commit, and finish with a two-line summary.
```

## 07. To t4 (p2)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T4, billing, in app/billing.py: requirement R-5 and the `report` contract in PLAN.md. Only edit app/billing.py.

You have no way to talk to the other agents; tell your developer anything the team should know.

Note from your developer: a cancelled delivery isn't free for us. Keep the 4.00 base fee of every cancelled delivery, and count it as revenue in the report.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 08. To t5 (p2)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T5, the command line, in cli/pigeon.py: requirement R-7 and every command in README.md's 'The command line' section. Use only Python's standard library or httpx. Only edit cli/pigeon.py.

You have no way to talk to the other agents; tell your developer anything the team should know.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 11. To t1 (p3)

```
Message from the lead to the whole team: One change for launch, a new requirement R-8. Express delivery. A quote or a delivery can be express. An express parcel pays an express fee of 50% of the delivery fee (before any promo discount). Birdseed Tax is then 8% of (delivery fee - promo discount + express fee), and the total includes the express fee. On the command line, quote and send take --express and print a new line, express_fee:, right after promo_discount: (0.00 when the parcel isn't express). Contracts: `quote-request` gains `express`: boolean; `delivery-request` gains `express`: boolean; `quote` gains `express_fee`: number. It concerns pricing (T2), dispatch (T3), command line (T5).

Update your part as needed, commit, and finish with a two-line summary.
```

## 12. To t2 (p3)

```
Message from the lead to the whole team: One change for launch, a new requirement R-8. Express delivery. A quote or a delivery can be express. An express parcel pays an express fee of 50% of the delivery fee (before any promo discount). Birdseed Tax is then 8% of (delivery fee - promo discount + express fee), and the total includes the express fee. On the command line, quote and send take --express and print a new line, express_fee:, right after promo_discount: (0.00 when the parcel isn't express). Contracts: `quote-request` gains `express`: boolean; `delivery-request` gains `express`: boolean; `quote` gains `express_fee`: number. It concerns pricing (T2), dispatch (T3), command line (T5).

Update your part as needed, commit, and finish with a two-line summary.
```

## 13. To t3 (p3)

```
Message from the lead to the whole team: One change for launch, a new requirement R-8. Express delivery. A quote or a delivery can be express. An express parcel pays an express fee of 50% of the delivery fee (before any promo discount). Birdseed Tax is then 8% of (delivery fee - promo discount + express fee), and the total includes the express fee. On the command line, quote and send take --express and print a new line, express_fee:, right after promo_discount: (0.00 when the parcel isn't express). Contracts: `quote-request` gains `express`: boolean; `delivery-request` gains `express`: boolean; `quote` gains `express_fee`: number. It concerns pricing (T2), dispatch (T3), command line (T5).

Update your part as needed, commit, and finish with a two-line summary.
```

## 14. To t4 (p3)

```
Message from the lead to the whole team: One change for launch, a new requirement R-8. Express delivery. A quote or a delivery can be express. An express parcel pays an express fee of 50% of the delivery fee (before any promo discount). Birdseed Tax is then 8% of (delivery fee - promo discount + express fee), and the total includes the express fee. On the command line, quote and send take --express and print a new line, express_fee:, right after promo_discount: (0.00 when the parcel isn't express). Contracts: `quote-request` gains `express`: boolean; `delivery-request` gains `express`: boolean; `quote` gains `express_fee`: number. It concerns pricing (T2), dispatch (T3), command line (T5).

Update your part as needed, commit, and finish with a two-line summary.
```

## 15. To t5 (p3)

```
Message from the lead to the whole team: One change for launch, a new requirement R-8. Express delivery. A quote or a delivery can be express. An express parcel pays an express fee of 50% of the delivery fee (before any promo discount). Birdseed Tax is then 8% of (delivery fee - promo discount + express fee), and the total includes the express fee. On the command line, quote and send take --express and print a new line, express_fee:, right after promo_discount: (0.00 when the parcel isn't express). Contracts: `quote-request` gains `express`: boolean; `delivery-request` gains `express`: boolean; `quote` gains `express_fee`: number. It concerns pricing (T2), dispatch (T3), command line (T5).

Update your part as needed, commit, and finish with a two-line summary.
```

## 16. To t6 (p3)

```
You are one of six developers' AI agents building PigeonPost together (read README.md and PLAN.md first). Each developer works on their own laptop, on their own git branch, and not all at the same time: some parts were started before yours and some start later. You can't see the others' code until everything is merged at the end.

Your part is T6, tracking, in app/tracking.py: requirement R-6 and the `tracking` contract in PLAN.md. Only edit app/tracking.py.

You have no way to talk to the other agents; tell your developer anything the team should know.

Message from the lead to the whole team: One change for launch, a new requirement R-8. Express delivery. A quote or a delivery can be express. An express parcel pays an express fee of 50% of the delivery fee (before any promo discount). Birdseed Tax is then 8% of (delivery fee - promo discount + express fee), and the total includes the express fee. On the command line, quote and send take --express and print a new line, express_fee:, right after promo_discount: (0.00 when the parcel isn't express). Contracts: `quote-request` gains `express`: boolean; `delivery-request` gains `express`: boolean; `quote` gains `express_fee`: number. It concerns pricing (T2), dispatch (T3), command line (T5).

Note from your developer: keep the field names short. Call the ETA field `eta_min`.

Build your first working version, commit it on your branch (git add, git commit), and finish with a two-line summary of what you built.
```

## 17. To t1 (p4)

```
Last call before everything is merged. Update your part as needed, commit, and finish with a two-line summary.
```

## 18. To t2 (p4)

```
Last call before everything is merged. Update your part as needed, commit, and finish with a two-line summary.
```

## 19. To t3 (p4)

```
Last call before everything is merged. Update your part as needed, commit, and finish with a two-line summary.
```

## 20. To t4 (p4)

```
Last call before everything is merged. Update your part as needed, commit, and finish with a two-line summary.
```

## 21. To t5 (p4)

```
Last call before everything is merged. Update your part as needed, commit, and finish with a two-line summary.
```

## 22. To t6 (p4)

```
Last call before everything is merged. Update your part as needed, commit, and finish with a two-line summary.
```

## 23. To fixer (fix1)

```
You are fixing a product after its parts, built separately by different AI agents, were merged (read README.md). Make the app work as a whole. These checks fail: (C9) the refund after cancelling, as the lead decided. Ran: cancel <second id> (the same command as C8). Expected: refund 8.91 (the total 11.88 less a 25% fee of 2.97). Got: delivery: 2
status: cancelled
refund: 11.88 (C11) revenue counts the cancellation fee the lead decided. Ran: report (the same command as C10). Expected: revenue 24.03 (8.10 + 12.96 + the 2.97 fee). Got: revenue: 25.06
confirmed: 2
cancelled: 1
flights: budget-bob=1
flights: express-edna=1 (C12) tax is charged after the promo discount. Ran: quote harbor 2.5 --promo COOCOO. Expected: delivery_fee 13.00, promo_discount 1.95, tax 0.88, total 11.93. Got: delivery_fee: 13.00
promo_discount: 1.95
express_fee: 0.00
tax: 1.04
total: 12.09 (C13) a delivery with a promo code is charged the same way. Ran: send harbor 1 --promo COOCOO; show <id>. Expected: promo_discount 1.50, tax 0.68, total 9.18, and show says total 9.18. Got: delivery_fee: 10.00
promo_discount: 1.50
express_fee: 0.00
tax: 0.80
total: 9.30
delivery: 4
bird: budget-bob
status: confirmed | delivery: 4
bird: budget-bob
status: confirmed
total: 9.30 (C18) birds shows payloads in kg. Ran: birds. Expected: four `bird:` lines: max_payload 1, 2, 3, 5 kg with the fleet's speeds and flights. Got: bird: budget-bob max_payload=1000 speed=36 flights=2
bird: express-edna max_payload=2000 speed=90 flights=3
bird: sir-flaps-a-lot max_payload=3000 speed=54 flights=2
bird: cargo-carl max_payload=5000 speed=45 flights=1 (C19) a heavy parcel goes to a bird that can carry it. Ran: send airport 4. Expected: bird cargo-carl, total 23.76. Got: delivery_fee: 22.00
promo_discount: 0.00
express_fee: 0.00
tax: 1.76
total: 23.76
delivery: 6
bird: express-edna
status: confirmed (C20) a parcel too heavy for every bird is refused. Ran: send harbor 6. Expected: an `error:` line and exit code 1. Got: exit 0: delivery_fee: 20.00
promo_discount: 0.00
express_fee: 0.00
tax: 1.60
total: 21.60
delivery: 7
bird: sir-flaps-a-lot
status: confirmed Commit when done; two-line summary.
```

## 24. To fixer (fix2)

```
These checks fail: (C14) an express quote. Ran: quote harbor 2.5 --express. Expected: delivery_fee 13.00, express_fee 6.50, tax 1.56, total 21.06. Got: delivery_fee: 13.00
promo_discount: 0.00
tax: 1.56
total: 21.06 (C15) an express delivery. Ran: send harbor 0.5 --express; show <id>. Expected: delivery_fee 9.00, express_fee 4.50, tax 1.08, total 14.58, and show says 14.58. Got: delivery_fee: 9.00
promo_discount: 0.00
tax: 1.08
total: 14.58
delivery: 5
bird: express-edna
status: confirmed | delivery: 5
bird: express-edna
status: confirmed
total: 14.58 Commit when done; two-line summary.
```

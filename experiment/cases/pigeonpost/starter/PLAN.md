# PigeonPost: the plan (version 1)

The lead wrote this plan before anyone started. README.md describes the product;
this page says who builds what and what the parts hand each other.

## Requirements

| Id | Requirement |
| --- | --- |
| R-1 | The roost knows the birds (handle, name, max payload in kg, speed in km/h, flights per day) and the destinations (code, name, distance from the roost in km). GET /birds lists the birds and GET /birds/{handle} returns one; GET /destinations lists the destinations and GET /destinations/{code} returns one. An unknown handle or code is a 404. |
| R-2 | POST /quote prices a parcel. Delivery fee = 4.00 + 0.50 per km to the destination + 2.00 per kg. Promo code COOCOO takes 15% off the delivery fee; any other code is an error (400). Birdseed Tax is 8% of (delivery fee - promo discount). Total = delivery fee - promo discount + tax. Money is in credits with two decimals; round half up to the cent wherever a fraction of a cent appears. |
| R-3 | POST /deliveries sends a parcel: it prices it by R-2, gives it to the bird with the smallest max payload that can carry the weight and still has a flight left today, and uses one of that bird's flights. A parcel heavier than every bird's max payload is refused, and so is a parcel when no bird that can carry it has a flight left (400). A weight is a multiple of 0.5 kg, from 0.5. |
| R-4 | GET /deliveries/{id} returns a delivery. POST /deliveries/{id}/cancel cancels it, gives the bird its flight back, and returns the delivery with what the customer gets back as refund (0 until a delivery is cancelled). GET /birds/{handle}/availability tells how many flights the bird has left today. An unknown delivery or bird is a 404. |
| R-5 | GET /report is the revenue report: what PigeonPost earned, how many deliveries are confirmed and cancelled, and the flights per bird (confirmed deliveries only). |
| R-6 | GET /deliveries/{id}/tracking tells where a delivery is: its status, its bird, and the ETA in whole minutes (distance to the destination / the bird's speed x 60, rounded half up). A cancelled delivery has ETA 0. An unknown delivery is a 404. |
| R-7 | The command line (cli/pigeon.py) offers every command in README.md's 'The command line' section over HTTP and prints exactly the keys listed there. `send` first asks for the quote (POST /quote) and prints it, then sends the parcel (POST /deliveries) and prints the delivery. |

## Tasks

One developer, with their AI agent, per task. Each task edits only its file.

| Task | Part | File | Requirements | Provides | Consumes |
| --- | --- | --- | --- | --- | --- |
| T1 | Roost | `app/roost.py` | R-1 | `bird`, `destination` | none |
| T2 | Pricing | `app/pricing.py` | R-2 | `quote-request`, `quote` | `destination` |
| T3 | Dispatch | `app/dispatch.py` | R-3, R-4 | `delivery-request`, `delivery`, `availability` | `bird`, `destination`, `quote-request`, `quote` |
| T4 | Billing | `app/billing.py` | R-5 | `report` | `delivery` |
| T5 | Command line | `cli/pigeon.py` | R-7 | none | `bird`, `destination`, `quote-request`, `quote`, `delivery-request`, `delivery`, `availability`, `report`, `tracking` |
| T6 | Tracking | `app/tracking.py` | R-6 | `tracking` | `bird`, `destination`, `delivery` |

## Contracts

What one part hands another, as JSON. Field names and types are exact.

| Contract | From | To | Fields |
| --- | --- | --- | --- |
| `bird` | T1 | T3, T5, T6 | `handle`: string, `name`: string, `max_payload`: number, `speed`: number, `flights_per_day`: integer |
| `destination` | T1 | T2, T3, T5, T6 | `code`: string, `name`: string, `distance_km`: number |
| `quote-request` | T2 | T3, T5 | `destination`: string, `weight_kg`: number, `promo`: string |
| `quote` | T2 | T3, T5 | `delivery_fee`: number, `promo_discount`: number, `tax`: number, `total`: number |
| `delivery-request` | T3 | T5 | `destination`: string, `weight_kg`: number, `promo`: string |
| `delivery` | T3 | T4, T5, T6 | `id`: integer, `destination`: string, `weight_kg`: number, `bird`: string, `status`: string, `total`: number, `refund`: number |
| `availability` | T3 | T5 | `bird`: string, `flights_left`: integer |
| `report` | T4 | T5 | `revenue`: number, `confirmed`: integer, `cancelled`: integer, `flights`: object |
| `tracking` | T6 | T5 | `delivery`: integer, `status`: string, `bird`: string, `eta_minutes`: integer |

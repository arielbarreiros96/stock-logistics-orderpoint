When one warehouse both sells and resupplies other warehouses, the resupply eats
the stock the sales draw on. Odoo forecasts `on hand + incoming - outgoing`, so
every resupply transfer counts against the hub the moment it is created, the
hub's own reordering rule sees a hole, and it buys its way out of it. The
transfers were never wrong on their own -- together they order far more than the
company ever needed.

This module lets you hold a quantity of a product back in a location. Automatic
replenishment may not draw on it. Everything else -- sales, manufacturing,
scrap, any transfer a person makes -- consumes it exactly as before.

## Example

The hub holds 100 units and reserves 30 for its own webshop sales. A shop's
reordering rule asks for 100.

| | Transfer created | Purchase triggered at the hub |
| --- | --- | --- |
| Odoo standard behaviour | 100 | yes, for the shortfall |
| This module | 70 | no |

The shop's rule still asks for 100. Next time the scheduler runs, whatever the
hub has recovered above 30 goes out, until the shop is served.

## What it is not

The reserve is **not** a stock reservation. It never touches
`reserved_quantity` on a quant, so nothing is withheld from a customer order.
It is a floor that automatic replenishment refuses to cross.

It also deals only in stock that is really on the shelf. Incoming quantities are
ignored on purpose -- goods on a purchase order cannot be sold, so they must not
be allowed to spend the reserve either -- and outgoing ones count for what they
have actually set aside rather than for what they asked for. What is left after
both is Odoo's **Free to Use**, and that is the number this module works from.

## Why not just split the location

Putting the buffer in a `WH/Stock/Webshop` sublocation and sourcing the resupply
route from a sibling needs no code at all -- but then every receipt, putaway and
count has to keep the physical split honest, and the buffer becomes a place
instead of a number one person can change in one field.

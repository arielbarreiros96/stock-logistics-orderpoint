## Seeing what replenishment can still move

Open a product's **Forecasted Report** and pick a warehouse. Where a reserve is
in force at that warehouse, a second line appears under the usual forecast:

> Available to replenish from WH/Stock — On Hand 100 − Committed 40 − Reserve 30 = **30**

It is a different sum from the forecast above it, which is why it gets its own
line. Every term is stock that is *actually there*, never stock that is merely
expected or merely wanted:

- Incoming quantities are left out, so the reserve cannot be spent against a
  purchase order that has not arrived.
- **Committed** is what other transfers have already set aside, not what they
  asked for: a delivery for 15 units with only 4 reserved has committed 4. It
  covers internal moves and manufacturing orders too, which is why it is not
  called *Outgoing* -- the **Outgoing** figure on the forecast line above will
  often be larger, because it counts demand. On Hand less Committed is Odoo's
  **Free to Use**.

The line is absent entirely on warehouses and products with no reserve, so the
report reads exactly as Odoo ships it everywhere else.

The graph below carries the same figure as a dashed **Available to Replenish**
line, running from today to the end of the window. A reserve that ends inside
the window steps the line up the day after it lifts, and one that starts later
steps it down on the day it begins. Only the reserve moves with the calendar;
the stock side is today's picture held steady, so the line starts at the figure
written above it and sits on the floor over the history behind it, the way the
forecast does. A reserve whose changes all fall beyond the window is left out of
the report altogether.

Reordering rules carry the same number as **Available at Source**, on the form
and as an optional column in the list next to *To Order*. When a rule keeps
asking and never gets served, that field is the reason. Where a route passes
through more than one hub, the tightest of them is shown.

The *Replenishment Reserves* list shows **On Hand**, **Committed** and
**Available to Replenish** per reserve, for scanning many products at once.

## What you will see

The reordering rule keeps showing the quantity it actually wants. Only the
transfer is smaller. That is deliberate -- the reserve is a limit on what the
source may give away today, not a correction to what the shop needs. The
quantity that did go out counts as in progress, so the next scheduler run asks
for the remainder and caps it again, until the shop is served.

Where several shops draw on the same location, each of their transfers is
capped at the same figure. The reserve limits what any one of them may ask
for; it does not decide which of them goes without, so two shops short at once
both get a transfer and the source shows more outgoing than it can serve. The
floor still holds -- the surplus is never reserved and never leaves -- and
which shop is actually served is settled when the transfers reserve.

## Letting a replenishment through

Transfers created by automatic replenishment out of an internal location are
marked *Respect Replenishment Reserve*. While the mark is on, **Check
Availability** reserves only what stands above the reserve -- otherwise the
routine availability check would hand the buffer over anyway, a day after the
transfer was carefully sized to avoid it.

- **Ignore Reserve** frees the replenishment and reserves it in full.
- **Respect Reserve** puts it back, handing back whatever it took above the
  floor.

Both act on the **whole chain** of transfers the replenishment created, so a
resupply that travels through a transit location is freed, or put back, in one
press from either end. Neither button appears on a transfer no reserve can
reach -- a leg drawing on transit, or a product nobody set a reserve for.

## What is not affected

- Reordering rules with the **Manual** trigger. Odoo does not stamp an
  orderpoint on what they procure, and neither does this module.
- Purchases. A buy rule sources from a vendor location, where no reserve can be
  set, so the purchase path is untouched.
- Anything that is not automatic replenishment: deliveries, manufacturing
  orders, scrap, transfers made by hand.

A reordering rule with the **Auto** trigger *is* capped even when a user presses
**Replenish** on it by hand. The rule is automatic; the button only makes it run
sooner.

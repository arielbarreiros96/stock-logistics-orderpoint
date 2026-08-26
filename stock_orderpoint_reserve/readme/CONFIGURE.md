Go to *Inventory > Configuration > Replenishment Reserves* and create a record:

- **Product** -- reserves are held per variant, because stock is. On a product
  with a single variant the smart button on the product form fills it in for
  you, so a database that never turned variants on never has to think about it.
- **Location** -- the reserve covers this location and everything below it.
- **Quantity** -- in the product's unit of measure.
- **From** / **To** -- the period the reserve is in force. Both are optional:
  leave them empty for a reserve that simply always applies, or fill in one end
  only for "from this day on" and "until this day, inclusive". Set *From* far
  enough ahead of a campaign: the reserve is judged on the day replenishment
  runs, and lead times are not added to it.

Reserves add up. A reserve of 50 on `WH/Stock` and another of 30 on
`WH/Stock/Shelf 1` hold 80 back from anything replenishing out of `Shelf 1`.
Two records for the same product, location and period are refused, though:
that is one reserve, and its quantity is the sum.

With no reserve recorded, this module changes nothing at all.

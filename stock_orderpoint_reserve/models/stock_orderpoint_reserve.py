# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockOrderpointReserve(models.Model):
    _name = "stock.orderpoint.reserve"
    _description = "Stock Orderpoint Reserve"

    active = fields.Boolean(default=True)
    product_id = fields.Many2one(
        comodel_name="product.product",
        required=True,
        ondelete="cascade",
        domain=[("is_storable", "=", True)],
    )
    location_id = fields.Many2one(
        comodel_name="stock.location",
        required=True,
        ondelete="cascade",
        domain=[("usage", "=", "internal")],
        help="The reserve covers this location and everything below it.",
    )
    quantity = fields.Float(
        required=True,
        digits="Product Unit",
        help="Quantity automatic replenishment may not draw on, in the "
        "product's unit of measure. Sales, manufacturing and anything a user "
        "does by hand still consume it freely.",
    )
    date_start = fields.Date(
        string="From",
        help="Left empty, the reserve has been in force since always.",
    )
    date_stop = fields.Date(
        string="To",
        help="Left empty, the reserve stays in force indefinitely.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )
    qty_available = fields.Float(
        string="On Hand",
        compute="_compute_qty_available_to_replenish",
        digits="Product Unit",
    )
    committed_qty = fields.Float(
        string="Committed",
        compute="_compute_qty_available_to_replenish",
        digits="Product Unit",
        help="Stock other transfers have already set aside. A delivery asking "
        "for 15 units with 4 reserved has taken 4.",
    )
    qty_available_to_replenish = fields.Float(
        string="Available to Replenish",
        compute="_compute_qty_available_to_replenish",
        digits="Product Unit",
        help="What automatic replenishment may still take out of this "
        "location: on hand, less what is committed, less the reserve. "
        "Incoming quantities are left out on purpose, and so is demand "
        "nothing was set aside for.",
    )

    _quantity_positive = models.Constraint(
        "CHECK(quantity > 0)",
        "The reserved quantity must be greater than 0.",
    )
    # COALESCE, and an index rather than a UNIQUE constraint: an open end is
    # stored as NULL, and Postgres counts two NULLs as different values, so a
    # plain UNIQUE waves through a second perpetual reserve on the same shelf.
    _product_location_unique = models.UniqueIndex(
        "(product_id, location_id,"
        " COALESCE(date_start, '-infinity'::date),"
        " COALESCE(date_stop, 'infinity'::date),"
        " COALESCE(company_id, 0))",
        "There is already a reserve for this product and location over the "
        "same period.",
    )

    @api.depends("product_id", "location_id")
    def _compute_display_name(self):
        for record in self:
            record.display_name = (
                f"{record.product_id.display_name} @ {record.location_id.display_name}"
            )

    @api.depends("product_id", "location_id", "quantity", "date_start", "date_stop")
    def _compute_qty_available_to_replenish(self):
        self.qty_available = 0.0
        self.committed_qty = 0.0
        self.qty_available_to_replenish = 0.0
        for location, records in self.grouped("location_id").items():
            if not location:
                continue
            products = records.product_id
            quantities = products.with_context(location=location.id).read(
                ["qty_available", "free_qty"]
            )
            quantities = {vals["id"]: vals for vals in quantities}
            replenishable = products._get_replenishable_qty(location)
            for record in records:
                vals = quantities.get(record.product_id.id) or {}
                record.qty_available = vals.get("qty_available", 0.0)
                record.committed_qty = record.qty_available - vals.get("free_qty", 0.0)
                record.qty_available_to_replenish = replenishable.get(
                    record.product_id.id, 0.0
                )

    @api.constrains("date_start", "date_stop")
    def _check_date_window(self):
        for record in self:
            if not record.date_start or not record.date_stop:
                continue
            if record.date_stop < record.date_start:
                raise ValidationError(
                    self.env._("The end date must not precede the start date.")
                )

    @api.model
    def _get_effective_reserves(self, products, location, reference_date):
        """What of each product may not be drawn out of `location`.

        Keyed by product id, and only for the products that actually carry a
        reserve. Records set on a parent location count too, and every record
        in force adds up.
        """
        if not products or not location:
            return {}
        groups = self._read_group(
            self._reserve_domain(products, location)
            + self._in_force_domain(reference_date),
            groupby=["product_id"],
            aggregates=["quantity:sum"],
        )
        return {product.id: quantity for product, quantity in groups}

    @api.model
    def _get_effective_reserve(self, product, location, reference_date):
        """The reserve one product carries in one location. See above."""
        reserves = self._get_effective_reserves(product, location, reference_date)
        return reserves.get(product.id, 0.0)

    @api.model
    def _reserve_domain(self, products, location):
        """Every reserve that can reach these products in this location."""
        return [
            ("product_id", "in", products.ids),
            ("location_id", "parent_of", location.id),
            ("company_id", "in", [False, *location.company_id.ids]),
        ]

    @api.model
    def _in_force_domain(self, date_from, date_to=None):
        """Records whose window overlaps ``[date_from, date_to]``.

        Either end of a record may be left open, and so may `date_to`, which
        then narrows the test to the single day `date_from`.
        """
        return [
            "|",
            ("date_start", "=", False),
            ("date_start", "<=", date_to or date_from),
            "|",
            ("date_stop", "=", False),
            ("date_stop", ">=", date_from),
        ]

    @api.model
    def _get_reserve_breakpoints(self, products, location, date_from, date_to):
        """The days within the window on which the reserve changes.

        Sorted, and always starting at `date_from`, so a caller can walk the
        list and know the reserve holds steady from each entry until the next.
        """
        if not products or not location or date_to < date_from:
            return [date_from]
        records = self.search(
            self._reserve_domain(products, location)
            + self._in_force_domain(date_from, date_to)
        )
        breakpoints = {date_from}
        for record in records:
            if record.date_start:
                breakpoints.add(record.date_start)
            if record.date_stop:
                breakpoints.add(record.date_stop + timedelta(days=1))
        return sorted(date for date in breakpoints if date_from <= date <= date_to)

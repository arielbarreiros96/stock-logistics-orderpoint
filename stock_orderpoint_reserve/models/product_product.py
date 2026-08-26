# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    orderpoint_reserve_ids = fields.One2many(
        comodel_name="stock.orderpoint.reserve",
        inverse_name="product_id",
    )
    orderpoint_reserve_count = fields.Integer(
        compute="_compute_orderpoint_reserve_count",
    )

    @api.depends("orderpoint_reserve_ids")
    def _compute_orderpoint_reserve_count(self):
        groups = self.env["stock.orderpoint.reserve"]._read_group(
            [("product_id", "in", self.ids)],
            groupby=["product_id"],
            aggregates=["__count"],
        )
        counts = {product.id: count for product, count in groups}
        for product in self:
            product.orderpoint_reserve_count = counts.get(product.id, 0)

    def action_open_orderpoint_reserves(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_orderpoint_reserve.action_stock_orderpoint_reserve"
        )
        action["domain"] = [("product_id", "in", self.ids)]
        action["context"] = {
            **self.env.context,
            "default_product_id": self.id if len(self) == 1 else False,
        }
        return action

    def _get_source_availability(self, location, reference_date=None, reserves=None):
        """What `location` can still give away, product by product.

        Every term is counted as fact and never as intent: goods that have not
        arrived are not there, and a delivery asking for 15 units with only 4
        reserved has taken 4 off the shelf, not 15. Odoo already keeps that
        number -- it is `free_qty`. Quantities come back in the product's uom.
        """
        if reserves is None:
            reserves = self.env["stock.orderpoint.reserve"]._get_effective_reserves(
                self, location, reference_date or fields.Date.context_today(self)
            )
        quantities = self.with_context(location=location.id).read(["free_qty"])
        return {
            vals["id"]: max(0.0, vals["free_qty"] - reserves.get(vals["id"], 0.0))
            for vals in quantities
        }

    def _get_source_availability_schedule(self, location, date_from, date_to):
        """`_get_source_availability`, redone on each day the reserve changes.

        A list of ``(date, {product id: quantity})`` in order, each entry
        holding until the next one. Only the reserve moves with the calendar:
        the stock side stays today's snapshot, so the first entry is always
        what the report shows now.
        """
        breakpoints = self.env["stock.orderpoint.reserve"]._get_reserve_breakpoints(
            self, location, date_from, date_to
        )
        return [
            (date, self._get_source_availability(location, reference_date=date))
            for date in breakpoints
        ]

    def _get_replenishable_qty(self, location, reference_date=None):
        """The same, for the products a reserve actually reaches.

        Everything else is left out: with nothing configured this module must
        leave replenishment exactly where Odoo left it.
        """
        reference_date = reference_date or fields.Date.context_today(self)
        reserves = self.env["stock.orderpoint.reserve"]._get_effective_reserves(
            self, location, reference_date
        )
        products = self.filtered(lambda product: product.id in reserves)
        if not products:
            return {}
        return products._get_source_availability(location, reserves=reserves)

# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from dateutil.relativedelta import relativedelta

from odoo import fields, models


class StockForecasted_Product_Product(models.AbstractModel):
    _inherit = "stock.forecasted_product_product"

    def _get_report_data(self, product_template_ids=False, product_ids=False):
        res = super()._get_report_data(
            product_template_ids=product_template_ids, product_ids=product_ids
        )
        res["orderpoint_reserve"] = self._get_orderpoint_reserve_data(
            product_template_ids, product_ids
        )
        return res

    def _get_orderpoint_reserve_data(self, product_template_ids, product_ids):
        """The reserve line for the warehouse the report is looking at.

        The forecast above it reads on hand + incoming - outgoing, all of it
        demand. This reads free to use - reserve, stock that is there and
        unclaimed, which is why it gets a line of its own rather than being
        folded into that one.

        False when no reserve touches this product over the window the graph
        draws, so a database that never set a reserve sees the report exactly
        as Odoo ships it.
        """
        products = self._get_products(product_template_ids, product_ids)
        location = self._get_warehouse().lot_stock_id
        if not products or not location:
            return False
        today = fields.Date.context_today(self)
        schedule = products._get_source_availability_schedule(
            location, today, self._get_orderpoint_reserve_horizon(today)
        )
        reserves = self.env["stock.orderpoint.reserve"]._get_effective_reserves(
            products, location, today
        )
        if not reserves and len(schedule) == 1:
            return False
        quantities = products.with_context(location=location.id).read(
            ["qty_available", "free_qty"]
        )
        qty_available = sum(vals["qty_available"] for vals in quantities)
        free_qty = sum(vals["free_qty"] for vals in quantities)
        return {
            "location": location.display_name,
            "qty_available": qty_available,
            "committed_qty": qty_available - free_qty,
            "reserve": sum(reserves.values()),
            # The first breakpoint is today, so the figure above the graph and
            # the first step of the line it draws can never disagree.
            "available_to_replenish": sum(schedule[0][1].values()),
            "schedule": self._get_orderpoint_reserve_steps(schedule),
        }

    def _get_orderpoint_reserve_horizon(self, today):
        """How far ahead to look: as far as the forecast graph draws."""
        months = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("stock.report_stock_quantity_period", default="3")
        )
        return today + relativedelta(months=months)

    def _get_orderpoint_reserve_steps(self, schedule):
        """The schedule as ``[date, quantity]`` steps for the graph.

        Days where the total does not actually move are dropped: a reserve
        expiring on one variant while another one starts is not a step.
        """
        precision = self.env["decimal.precision"].precision_get("Product Unit")
        steps = []
        for date, availability in schedule:
            quantity = round(sum(availability.values()), precision)
            if steps and steps[-1][1] == quantity:
                continue
            steps.append([fields.Date.to_string(date), quantity])
        return steps

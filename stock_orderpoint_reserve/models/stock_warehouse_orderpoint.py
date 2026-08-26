# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import api, fields, models


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    qty_available_at_source = fields.Float(
        string="Available at Source",
        compute="_compute_qty_available_at_source",
        digits="Product Unit",
        help="What the location this rule draws on can still hand over: its "
        "on hand quantity, less what is already committed to leave, less any "
        "replenishment reserve. Empty when the rule is supplied from outside "
        "the company, a purchase for instance.",
    )

    def _get_orderpoint_reserve_supply_rules(self):
        """Every rule that feeds this one, all the way back to the origin.

        The chain Odoo resolved for lead times is only the start of it. Core
        drops the route on each step it takes back up the chain, and an
        inter-warehouse transit belongs to no warehouse, so there is nothing
        left to find a rule by and the walk stops there: `rule_ids` holds the
        leg into the shop and never reaches the warehouse handing the goods
        over. Finishing the walk here, with the route still in hand, is what
        lets a reserve at that warehouse be seen at all.

        Only a rule that orders its own supply is followed any further, which
        is where core stops too. The one that takes the goods off a shelf ends
        the chain: asking what fills that shelf leads into the warehouse's own
        receipts, which this replenishment never waits for.
        """
        self.ensure_one()
        rules = self.env["stock.rule"]
        frontier = self.rule_ids
        while frontier:
            rules |= frontier
            chained = frontier.filtered(
                lambda rule: rule.procure_method == "make_to_order"
            )
            found = self.env["stock.rule"]
            for location in chained.location_src_id:
                found |= self.product_id._get_rules_from_location(
                    location, route_ids=self.route_id
                )
            frontier = found - rules
        return rules

    def _get_orderpoint_reserve_source_locations(self):
        """The internal locations this rule's supply chain draws stock from.

        Every hop of it, because a reserve anywhere along the way holds the
        replenishment back. A buy rule sources from a vendor location and
        drops out, which is why the purchase path needs no special case.
        """
        self.ensure_one()
        return self._get_orderpoint_reserve_supply_rules().location_src_id.filtered(
            lambda location: location.usage == "internal"
        )

    def _get_orderpoint_reserve_origin_locations(self):
        """Of those, the ones the chain itself does not fill.

        A staging location the goods only pass through stands empty by design,
        and would otherwise read as the tightest link in every multi step
        route. What the chain can hand over is decided where it starts.
        """
        self.ensure_one()
        rules = self._get_orderpoint_reserve_supply_rules()
        sources = rules.location_src_id.filtered(
            lambda location: location.usage == "internal"
        )
        return sources - rules.location_dest_id

    @api.depends("product_id", "location_id", "route_id", "product_uom")
    def _compute_qty_available_at_source(self):
        """Where a chain starts in more than one internal location, the
        tightest of them is what it can actually get, so that is what is
        shown."""
        self.qty_available_at_source = 0.0
        orderpoints_by_location = defaultdict(lambda: self.browse())
        for orderpoint in self:
            for location in orderpoint._get_orderpoint_reserve_origin_locations():
                orderpoints_by_location[location] |= orderpoint
        tightest = {}
        for location, orderpoints in orderpoints_by_location.items():
            available = orderpoints.product_id._get_source_availability(location)
            for orderpoint in orderpoints:
                quantity = available.get(orderpoint.product_id.id)
                if quantity is None:
                    continue
                quantity = orderpoint.product_id.uom_id._compute_quantity(
                    quantity, orderpoint.product_uom, rounding_method="DOWN"
                )
                current = tightest.get(orderpoint.id)
                tightest[orderpoint.id] = (
                    quantity if current is None else min(current, quantity)
                )
        for orderpoint in self:
            orderpoint.qty_available_at_source = tightest.get(orderpoint.id, 0.0)

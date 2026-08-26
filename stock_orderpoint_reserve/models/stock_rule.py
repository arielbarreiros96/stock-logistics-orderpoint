# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import api, models


class StockRule(models.Model):
    _inherit = "stock.rule"

    @api.model
    def run(self, procurements, raise_user_error=True):
        return super().run(
            self._apply_orderpoint_reserve(procurements),
            raise_user_error=raise_user_error,
        )

    @api.model
    def _apply_orderpoint_reserve(self, procurements):
        """Return `procurements`, with the automatic ones capped by the reserve.

        A transfer sized to the reserve never counts as outgoing for more than
        the source can spare, which is what stops that warehouse from buying
        its way out of a hole it dug itself.

        Every rule drawing on the same location is offered the same headroom,
        never a slice of it. Spending it as it is handed out would leave this
        module deciding which shop goes without, in whatever order the
        scheduler happened to reach them -- an allocation it was never asked to
        make, and the arrival order a weighting module exists to replace. Who
        actually gets the goods is settled at reservation, against live quants
        and this same floor.

        The trade is that while several rules are short at once the source
        reads more outgoing than it can serve. The floor still holds: the
        surplus is never reserved and never leaves.

        Odoo stamps ``orderpoint_id`` in the procurement values for automatic
        reordering rules and only for those, so a manual rule, a sale order and
        a hand made transfer all pass through untouched. A capped quantity of
        zero is left in place rather than dropped: ``_skip_procurement``
        already discards those, which is quieter than raising.
        """
        indexes_by_location = defaultdict(list)
        for index, procurement in enumerate(procurements):
            orderpoint = procurement.values.get("orderpoint_id")
            if not orderpoint:
                continue
            for location in orderpoint._get_orderpoint_reserve_source_locations():
                indexes_by_location[location].append(index)
        if not indexes_by_location:
            return procurements

        procurements = list(procurements)
        for location, indexes in indexes_by_location.items():
            products = self.env["product.product"].browse(
                {procurements[index].product_id.id for index in indexes}
            )
            available = products._get_replenishable_qty(location)
            for index in indexes:
                procurement = procurements[index]
                product = procurement.product_id
                if product.id not in available:
                    continue
                asked = procurement.product_uom._compute_quantity(
                    procurement.product_qty, product.uom_id
                )
                granted = min(asked, available[product.id])
                if product.uom_id.compare(granted, asked) < 0:
                    procurements[index] = procurement._replace(
                        product_qty=product.uom_id._compute_quantity(
                            granted, procurement.product_uom, rounding_method="DOWN"
                        )
                    )
        return procurements

    def _get_stock_move_values(
        self,
        product_id,
        product_qty,
        product_uom,
        location_dest_id,
        name,
        origin,
        company_id,
        values,
    ):
        """Mark the moves automatic replenishment creates.

        The same values dict travels down a multi step route, so one place
        marks the whole chain. Only the legs drawing on an internal location
        are marked: a reserve cannot be set anywhere else, so the transit leg
        would carry a mark that constrains nothing and a button that frees
        nothing.
        """
        move_values = super()._get_stock_move_values(
            product_id,
            product_qty,
            product_uom,
            location_dest_id,
            name,
            origin,
            company_id,
            values,
        )
        move_values["orderpoint_reserve_guard"] = (
            bool(values.get("orderpoint_id"))
            and self.location_src_id.usage == "internal"
        )
        return move_values

    def _push_prepare_move_copy_values(self, move_to_copy, new_date):
        move_values = super()._push_prepare_move_copy_values(move_to_copy, new_date)
        move_values["orderpoint_reserve_guard"] = (
            move_to_copy.orderpoint_reserve_guard
            and move_to_copy.location_dest_id.usage == "internal"
        )
        return move_values

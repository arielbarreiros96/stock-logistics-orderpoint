# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    orderpoint_reserve_guard = fields.Boolean(
        string="Respect Replenishment Reserve",
        copy=False,
        help="Set on the transfers automatic replenishment creates. While it "
        "is set, this move reserves only what stands above the reserve of its "
        "source location. Clear it to let the move reserve like any other.",
    )

    def _update_reserved_quantity(
        self,
        need,
        location_id,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=True,
    ):
        """The one funnel every make to stock reservation passes through.

        Capping the quantity when the transfer was created is not enough on its
        own: stock moves on between then and the moment it is reserved, and the
        availability check would make up the difference out of the reserve.
        """
        need = self._cap_need_to_orderpoint_reserve(need, location_id, strict)
        if self.product_id.uom_id.is_zero(need):
            return 0.0
        return super()._update_reserved_quantity(
            need,
            location_id,
            lot_id=lot_id,
            package_id=package_id,
            owner_id=owner_id,
            strict=strict,
        )

    def _cap_need_to_orderpoint_reserve(self, need, location_id, strict):
        """What this move may still take, once the reserve is set aside.

        Quants are read live rather than through the forecast, so the floor
        holds even as earlier moves in the same reservation run eat the source.
        """
        self.ensure_one()
        if not self.orderpoint_reserve_guard or self._should_bypass_reservation():
            return need
        reserve = self.env["stock.orderpoint.reserve"]._get_effective_reserve(
            self.product_id, location_id, fields.Date.context_today(self)
        )
        if not reserve:
            return need
        available = self.env["stock.quant"]._get_available_quantity(
            self.product_id, location_id, strict=strict
        )
        return min(need, max(0.0, available - reserve))

    def _get_orderpoint_reserved_products(self):
        """Of these moves, the products a reserve actually reaches today."""
        reserve_model = self.env["stock.orderpoint.reserve"]
        reference_date = fields.Date.context_today(self)
        products = self.env["product.product"]
        for location, moves in self.grouped("location_id").items():
            reserves = reserve_model._get_effective_reserves(
                moves.product_id, location, reference_date
            )
            products |= moves.product_id.filtered(
                lambda product, reserves=reserves: product.id in reserves
            )
        return products

    def _get_orderpoint_reserve_chain(self):
        """Every move the same replenishment made, followed both ways.

        Only the leg drawing on the reserve is ever held back, so freeing that
        leg alone would leave the rest of the chain marked. The walk stays
        inside the reordering rules of the moves it started from, so a delivery
        chained onto the same goods is never dragged along.
        """
        orderpoints = self.orderpoint_id
        chain = self.browse()
        frontier = self
        while frontier:
            chain |= frontier
            neighbours = (frontier.move_orig_ids | frontier.move_dest_ids) - chain
            frontier = neighbours.filtered(
                lambda move: move.orderpoint_id and move.orderpoint_id in orderpoints
            )
        return chain.filtered(lambda move: move.state not in ("done", "cancel"))

    def action_ignore_orderpoint_reserve(self):
        chain = self._get_orderpoint_reserve_chain()
        chain.orderpoint_reserve_guard = False
        return chain._action_assign()

    def action_respect_orderpoint_reserve(self):
        chain = self._get_orderpoint_reserve_chain()
        chain.filtered(
            lambda move: move.location_id.usage == "internal"
        ).orderpoint_reserve_guard = True
        # Unreserved first, otherwise the mark goes back on while what the move
        # took above the floor stays gone.
        chain._do_unreserve()
        return chain._action_assign()

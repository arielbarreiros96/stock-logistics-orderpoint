# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    orderpoint_reserve_guard = fields.Boolean(
        compute="_compute_orderpoint_reserve_state",
    )
    orderpoint_reserve_released = fields.Boolean(
        compute="_compute_orderpoint_reserve_state",
    )

    @api.depends("move_ids.orderpoint_reserve_guard", "move_ids.orderpoint_id")
    def _compute_orderpoint_reserve_state(self):
        """Which of the two buttons this transfer should offer, if either.

        Neither is offered on a transfer no reserve can reach: a leg drawing on
        transit, or a product nobody set a reserve for. A button that frees
        nothing sends the user to the wrong transfer.
        """
        self.orderpoint_reserve_guard = False
        self.orderpoint_reserve_released = False
        replenishment = self.move_ids.filtered(
            lambda move: (
                move.orderpoint_id
                and move.state not in ("done", "cancel")
                and move.location_id.usage == "internal"
            )
        )
        reserved_products = replenishment._get_orderpoint_reserved_products()
        for picking in self:
            moves = replenishment.filtered(
                lambda move, picking=picking: (
                    move.picking_id == picking and move.product_id in reserved_products
                )
            )
            picking.orderpoint_reserve_guard = any(
                moves.mapped("orderpoint_reserve_guard")
            )
            picking.orderpoint_reserve_released = bool(moves) and not any(
                moves.mapped("orderpoint_reserve_guard")
            )

    def action_ignore_orderpoint_reserve(self):
        self.move_ids.action_ignore_orderpoint_reserve()
        return True

    def action_respect_orderpoint_reserve(self):
        self.move_ids.action_respect_orderpoint_reserve()
        return True

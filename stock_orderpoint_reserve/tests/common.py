# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import TransactionCase

from odoo.addons.base.tests.common import DISABLED_MAIL_CONTEXT


class OrderpointReserveCommon(TransactionCase):
    """A hub warehouse that resupplies a shop, the way the module is meant."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, **DISABLED_MAIL_CONTEXT))

        # Granted up front: adding a second warehouse otherwise flips the
        # group through res.config.settings, which drags half the database in.
        cls.env.ref("base.group_user").implied_ids |= cls.env.ref(
            "stock.group_stock_multi_locations"
        )

        cls.hub = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        cls.shop = cls.env["stock.warehouse"].create(
            {
                "name": "Shop",
                "code": "SHOP",
                "resupply_wh_ids": [Command.set(cls.hub.ids)],
            }
        )
        cls.resupply_route = cls.env["stock.route"].search(
            [
                ("supplied_wh_id", "=", cls.shop.id),
                ("supplier_wh_id", "=", cls.hub.id),
            ]
        )
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")

        cls.product = cls.env["product.product"].create(
            {
                "name": "Pool Pump",
                "is_storable": True,
                "route_ids": [Command.set(cls.resupply_route.ids)],
            }
        )
        cls.orderpoint = cls.env["stock.warehouse.orderpoint"].create(
            {
                "warehouse_id": cls.shop.id,
                "location_id": cls.shop.lot_stock_id.id,
                "product_id": cls.product.id,
                "product_min_qty": 100.0,
                "product_max_qty": 100.0,
                "replenishment_uom_id": False,
                "trigger": "auto",
                "route_id": cls.resupply_route.id,
            }
        )

    # -- helpers ----------------------------------------------------------

    @classmethod
    def _set_hub_stock(cls, quantity, product=None):
        cls.env["stock.quant"]._update_available_quantity(
            product or cls.product, cls.hub.lot_stock_id, quantity
        )

    @classmethod
    def _create_reserve(cls, quantity, location=None, product=None, **values):
        """Perpetual unless the caller says otherwise, as in the interface."""
        return cls.env["stock.orderpoint.reserve"].create(
            {
                "product_id": (product or cls.product).id,
                "location_id": (location or cls.hub.lot_stock_id).id,
                "quantity": quantity,
                **values,
            }
        )

    def _run_replenishment(self, orderpoint=None):
        """What the scheduler does, narrowed to one reordering rule.

        Mirrors ``stock.rule._run_scheduler_tasks``: recompute, then procure.
        """
        orderpoint = orderpoint or self.orderpoint
        self.env.flush_all()
        self.env.invalidate_all()
        orderpoint._compute_qty_to_order_computed()
        orderpoint._procure_orderpoint_confirm(company_id=self.env.company)
        self.env.flush_all()

    def _hub_moves(self, product=None):
        """The replenishment moves leaving the hub."""
        return self.env["stock.move"].search(
            [
                ("product_id", "=", (product or self.product).id),
                ("location_id", "=", self.hub.lot_stock_id.id),
                ("state", "not in", ("done", "cancel")),
            ]
        )

    def _create_outgoing_move(self, quantity, assign=True):
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": quantity,
                "location_id": self.hub.lot_stock_id.id,
                "location_dest_id": self.customer_location.id,
                "picking_type_id": self.hub.out_type_id.id,
            }
        )
        move._action_confirm()
        if assign:
            move._action_assign()
        return move

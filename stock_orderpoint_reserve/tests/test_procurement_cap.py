# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command

from .common import OrderpointReserveCommon


class TestProcurementCap(OrderpointReserveCommon):
    """What automatic replenishment is allowed to ask the hub for."""

    def test_no_reserve_leaves_odoo_alone(self):
        self._set_hub_stock(100.0)
        self._run_replenishment()
        self.assertEqual(self._hub_moves().product_uom_qty, 100.0)

    def test_reserve_caps_the_transfer(self):
        self._set_hub_stock(100.0)
        self._create_reserve(30.0)
        self._run_replenishment()
        self.assertEqual(self._hub_moves().product_uom_qty, 70.0)

    def test_a_multi_step_hub_is_still_capped(self):
        """A hub that stages its deliveries hands the goods over in two legs.

        Odoo resolves the chain only as far as the inter-warehouse transit,
        which belongs to no warehouse and leaves it nothing to go on, so the
        leg that draws on the reserve is never in `rule_ids` and the reserve
        used to go unseen entirely.
        """
        self.hub.delivery_steps = "pick_ship"
        self.orderpoint.invalidate_recordset()
        self.assertIn(
            self.hub.lot_stock_id,
            self.orderpoint._get_orderpoint_reserve_source_locations(),
        )
        self._set_hub_stock(100.0)
        self._create_reserve(30.0)
        self._run_replenishment()
        self.assertEqual(sum(self._hub_moves().mapped("product_uom_qty")), 70.0)

    def test_nothing_above_the_reserve_creates_nothing(self):
        self._set_hub_stock(30.0)
        self._create_reserve(30.0)
        self._run_replenishment()
        self.assertFalse(self._hub_moves())
        self.assertFalse(
            self.env["mail.activity"].search_count(
                [("res_id", "=", self.product.product_tmpl_id.id)]
            )
        )

    def test_outgoing_is_taken_off_first(self):
        self._set_hub_stock(100.0)
        self._create_outgoing_move(40.0)
        self._create_reserve(30.0)
        self._run_replenishment()
        replenishment = self._hub_moves().filtered(
            lambda move: move.location_dest_id.usage != "customer"
        )
        self.assertEqual(replenishment.product_uom_qty, 30.0)

    def test_incoming_does_not_spend_the_reserve(self):
        self._set_hub_stock(100.0)
        incoming = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 500.0,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.hub.lot_stock_id.id,
                "picking_type_id": self.hub.in_type_id.id,
            }
        )
        incoming._action_confirm()
        self._create_reserve(30.0)
        self._run_replenishment()
        self.assertEqual(
            self.product.with_context(location=self.hub.lot_stock_id.id).incoming_qty,
            500.0,
        )
        self.assertEqual(self._hub_moves().product_uom_qty, 70.0)

    def test_the_headroom_is_offered_to_every_rule(self):
        """The reserve caps what each shop may ask for, not which shop asks.

        Slicing the headroom between them would starve whichever the scheduler
        reached second, in an order nobody chose, and leave nothing for a
        weighting module to arbitrate: the shop that went without would have no
        transfer at all.
        """
        other_shop = self.env["stock.warehouse"].create(
            {
                "name": "Other Shop",
                "code": "SHOP2",
                "resupply_wh_ids": [Command.set(self.hub.ids)],
            }
        )
        other_route = self.env["stock.route"].search(
            [
                ("supplied_wh_id", "=", other_shop.id),
                ("supplier_wh_id", "=", self.hub.id),
            ]
        )
        self.product.route_ids = [Command.link(other_route.id)]
        other_orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {
                "warehouse_id": other_shop.id,
                "location_id": other_shop.lot_stock_id.id,
                "product_id": self.product.id,
                "product_min_qty": 100.0,
                "product_max_qty": 100.0,
                "replenishment_uom_id": False,
                "trigger": "auto",
                "route_id": other_route.id,
            }
        )
        self._set_hub_stock(100.0)
        self._create_reserve(30.0)
        self._run_replenishment(self.orderpoint | other_orderpoint)
        # Both draw on the same transit, so Odoo merges the two legs out of
        # the hub into one; what matters is that neither shop went without.
        self.assertEqual(sum(self._hub_moves().mapped("product_uom_qty")), 140.0)
        for orderpoint in self.orderpoint | other_orderpoint:
            self.assertTrue(
                self.env["stock.move"].search_count(
                    [("orderpoint_id", "=", orderpoint.id)]
                ),
                f"{orderpoint.display_name} was left without a transfer",
            )

    def test_manual_trigger_is_not_capped(self):
        self._set_hub_stock(100.0)
        self._create_reserve(30.0)
        self.orderpoint.trigger = "manual"
        self._run_replenishment()
        self.assertEqual(self._hub_moves().product_uom_qty, 100.0)

    def test_replenishment_moves_are_marked(self):
        self._set_hub_stock(100.0)
        self._run_replenishment()
        self.assertTrue(self._hub_moves().orderpoint_reserve_guard)

    def test_manual_transfers_are_not_marked(self):
        self._set_hub_stock(100.0)
        self.assertFalse(self._create_outgoing_move(40.0).orderpoint_reserve_guard)

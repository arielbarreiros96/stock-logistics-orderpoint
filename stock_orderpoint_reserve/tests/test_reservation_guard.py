# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .common import OrderpointReserveCommon


class TestReservationGuard(OrderpointReserveCommon):
    """What a marked transfer is allowed to take, once stock has moved on."""

    def _create_replenishment_move(self, quantity, guard=True):
        """A transfer sized when the hub was fuller than it is now."""
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": quantity,
                "location_id": self.hub.lot_stock_id.id,
                "location_dest_id": self.shop.lot_stock_id.id,
                "picking_type_id": self.hub.int_type_id.id,
                "orderpoint_reserve_guard": guard,
            }
        )
        move._action_confirm()
        move._action_assign()
        return move

    def test_marked_move_stops_at_the_reserve(self):
        self._set_hub_stock(50.0)
        self._create_reserve(30.0)
        move = self._create_replenishment_move(70.0)
        self.assertEqual(move.quantity, 20.0)
        self.assertEqual(move.state, "partially_available")

    def test_marked_move_takes_nothing_when_the_reserve_is_all_there_is(self):
        self._set_hub_stock(30.0)
        self._create_reserve(30.0)
        move = self._create_replenishment_move(70.0)
        self.assertEqual(move.quantity, 0.0)

    def test_unmarked_move_reserves_freely(self):
        self._set_hub_stock(50.0)
        self._create_reserve(30.0)
        move = self._create_replenishment_move(70.0, guard=False)
        self.assertEqual(move.quantity, 50.0)

    def test_customer_delivery_reserves_freely(self):
        self._set_hub_stock(50.0)
        self._create_reserve(30.0)
        move = self._create_outgoing_move(50.0)
        self.assertEqual(move.quantity, 50.0)

    def test_ignoring_the_reserve_releases_the_move(self):
        self._set_hub_stock(50.0)
        self._create_reserve(30.0)
        move = self._create_replenishment_move(70.0)
        self.assertEqual(move.quantity, 20.0)

        move.picking_id.action_ignore_orderpoint_reserve()
        self.assertFalse(move.orderpoint_reserve_guard)
        self.assertEqual(move.quantity, 50.0)

    def test_check_availability_keeps_respecting_the_reserve(self):
        """The routine availability check must not undo the sizing."""
        self._set_hub_stock(50.0)
        self._create_reserve(30.0)
        move = self._create_replenishment_move(70.0)
        move.picking_id.action_assign()
        self.assertEqual(move.quantity, 20.0)

    def test_the_transit_leg_is_not_marked(self):
        """A reserve cannot be set on transit, so the leg must not claim one."""
        self._set_hub_stock(100.0)
        self._create_reserve(30.0)
        self._run_replenishment()
        moves = self.env["stock.move"].search(
            [("orderpoint_id", "=", self.orderpoint.id)]
        )
        from_hub = moves.filtered(
            lambda move: move.location_id == self.hub.lot_stock_id
        )
        from_transit = moves - from_hub
        self.assertTrue(from_hub.orderpoint_reserve_guard)
        self.assertTrue(from_transit)
        self.assertFalse(any(from_transit.mapped("orderpoint_reserve_guard")))
        self.assertFalse(from_transit.picking_id.orderpoint_reserve_guard)

    def test_releasing_one_transfer_releases_the_chain(self):
        self._set_hub_stock(100.0)
        self._create_reserve(30.0)
        self._run_replenishment()
        moves = self.env["stock.move"].search(
            [("orderpoint_id", "=", self.orderpoint.id)]
        )
        from_hub = moves.filtered(
            lambda move: move.location_id == self.hub.lot_stock_id
        )
        self.assertGreater(len(moves), 1, "expected a chained resupply")

        from_hub.picking_id.action_ignore_orderpoint_reserve()
        self.assertFalse(any(moves.mapped("orderpoint_reserve_guard")))
        self.assertEqual(from_hub.quantity, from_hub.product_uom_qty)

    def test_the_chain_can_be_put_back_under_the_reserve(self):
        self._set_hub_stock(100.0)
        self._create_reserve(30.0)
        move = self._create_replenishment_move(90.0)
        move.orderpoint_id = self.orderpoint
        self.assertEqual(move.quantity, 70.0)

        move.picking_id.action_ignore_orderpoint_reserve()
        self.assertEqual(move.quantity, 90.0)
        self.assertTrue(move.picking_id.orderpoint_reserve_released)

        move.picking_id.action_respect_orderpoint_reserve()
        self.assertTrue(move.orderpoint_reserve_guard)
        self.assertEqual(move.quantity, 70.0)

    def test_a_delivery_chained_on_is_left_alone(self):
        """The walk stays inside the reordering rule that started it."""
        self._set_hub_stock(100.0)
        self._create_reserve(30.0)
        replenishment = self._create_replenishment_move(90.0)
        replenishment.orderpoint_id = self.orderpoint
        delivery = self._create_outgoing_move(5.0)
        delivery.move_orig_ids = replenishment

        replenishment.picking_id.action_ignore_orderpoint_reserve()
        self.assertEqual(replenishment._get_orderpoint_reserve_chain(), replenishment)
        self.assertNotIn(delivery, replenishment._get_orderpoint_reserve_chain())

    def test_no_reserve_leaves_reservation_alone(self):
        self._set_hub_stock(50.0)
        move = self._create_replenishment_move(70.0)
        self.assertEqual(move.quantity, 50.0)

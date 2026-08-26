# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import fields

from .common import OrderpointReserveCommon


class TestVisibility(OrderpointReserveCommon):
    """Seeing what replenishment can still move, without doing the sum."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.context_today(cls.env["stock.orderpoint.reserve"])

    def _forecast(self, warehouse=None):
        return (
            self.env["stock.forecasted_product_product"]
            .with_context(warehouse_id=(warehouse or self.hub).id)
            ._get_report_data(product_ids=self.product.ids)
        )

    def test_report_line_is_absent_without_a_reserve(self):
        self._set_hub_stock(100.0)
        self.assertFalse(self._forecast()["orderpoint_reserve"])

    def test_report_line_shows_the_sum(self):
        self._set_hub_stock(100.0)
        self._create_outgoing_move(40.0)
        self._create_reserve(30.0)
        line = self._forecast()["orderpoint_reserve"]
        self.assertEqual(line["qty_available"], 100.0)
        self.assertEqual(line["committed_qty"], 40.0)
        self.assertEqual(line["reserve"], 30.0)
        self.assertEqual(line["available_to_replenish"], 30.0)
        self.assertEqual(line["location"], self.hub.lot_stock_id.display_name)

    def test_demand_nothing_was_set_aside_for_has_taken_nothing(self):
        """A delivery someone unreserved has handed the stock back."""
        self._set_hub_stock(100.0)
        self._create_outgoing_move(40.0)._do_unreserve()
        self._create_reserve(30.0)
        line = self._forecast()["orderpoint_reserve"]
        self.assertEqual(line["committed_qty"], 0.0)
        self.assertEqual(line["available_to_replenish"], 70.0)

    def test_a_delivery_counts_for_what_it_actually_took(self):
        """Asking for 50 with 20 on the shelf takes 20, not 50."""
        self._set_hub_stock(20.0)
        move = self._create_outgoing_move(50.0)
        self.assertEqual(move.quantity, 20.0, "the move can only reserve what is there")
        self._create_reserve(5.0)
        line = self._forecast()["orderpoint_reserve"]
        self.assertEqual(line["committed_qty"], 20.0)
        self.assertEqual(line["available_to_replenish"], 0.0)

    def test_report_line_is_per_warehouse(self):
        """A reserve on the hub says nothing about the shop."""
        self._set_hub_stock(100.0)
        self._create_reserve(30.0)
        self.assertTrue(self._forecast()["orderpoint_reserve"])
        self.assertFalse(self._forecast(warehouse=self.shop)["orderpoint_reserve"])

    def test_report_line_reaches_the_product_template_report(self):
        self._set_hub_stock(100.0)
        self._create_reserve(30.0)
        data = (
            self.env["stock.forecasted_product_template"]
            .with_context(warehouse_id=self.hub.id)
            ._get_report_data(product_template_ids=self.product.product_tmpl_id.ids)
        )
        self.assertEqual(data["orderpoint_reserve"]["available_to_replenish"], 70.0)

    # -- the schedule the graph draws --------------------------------------

    def test_perpetual_reserve_draws_one_flat_step(self):
        self._set_hub_stock(100.0)
        self._create_reserve(30.0)
        line = self._forecast()["orderpoint_reserve"]
        self.assertEqual(line["schedule"], [[str(self.today), 70.0]])

    def test_schedule_steps_up_the_day_after_the_reserve_expires(self):
        self._set_hub_stock(100.0)
        stop = self.today + timedelta(days=7)
        self._create_reserve(30.0, date_stop=stop)
        line = self._forecast()["orderpoint_reserve"]
        self.assertEqual(
            line["schedule"],
            [[str(self.today), 70.0], [str(stop + timedelta(days=1)), 100.0]],
        )

    def test_schedule_starts_at_what_the_line_above_it_says(self):
        self._set_hub_stock(100.0)
        self._create_outgoing_move(40.0)
        self._create_reserve(30.0, date_stop=self.today + timedelta(days=7))
        line = self._forecast()["orderpoint_reserve"]
        self.assertEqual(line["schedule"][0], [str(self.today), 30.0])
        self.assertEqual(line["available_to_replenish"], 30.0)

    def test_a_reserve_starting_later_is_reported_before_it_bites(self):
        """Nothing is held back yet, but the drop is already on the graph."""
        self._set_hub_stock(100.0)
        start = self.today + timedelta(days=5)
        self._create_reserve(30.0, date_start=start)
        line = self._forecast()["orderpoint_reserve"]
        self.assertEqual(line["reserve"], 0.0)
        self.assertEqual(line["available_to_replenish"], 100.0)
        self.assertEqual(
            line["schedule"], [[str(self.today), 100.0], [str(start), 70.0]]
        )

    def test_a_reserve_beyond_the_horizon_is_left_out(self):
        self._set_hub_stock(100.0)
        self._create_reserve(30.0, date_start=self.today + timedelta(days=400))
        self.assertFalse(self._forecast()["orderpoint_reserve"])

    def test_an_expired_reserve_is_left_out(self):
        self._set_hub_stock(100.0)
        self._create_reserve(
            30.0,
            date_start=self.today - timedelta(days=30),
            date_stop=self.today - timedelta(days=1),
        )
        self.assertFalse(self._forecast()["orderpoint_reserve"])

    def test_orderpoint_shows_what_the_source_can_give(self):
        self._set_hub_stock(100.0)
        self._create_outgoing_move(40.0)
        self._create_reserve(30.0)
        self.orderpoint.invalidate_recordset()
        self.assertEqual(self.orderpoint.qty_available_at_source, 30.0)

    def test_orderpoint_reports_where_a_staged_chain_starts(self):
        """A staging location the goods pass through stands empty by design.

        Reading it as the tightest link would report nothing available on
        every warehouse that does not ship in one step.
        """
        self.hub.delivery_steps = "pick_ship"
        self._set_hub_stock(100.0)
        self._create_reserve(30.0)
        self.orderpoint.invalidate_recordset()
        self.assertEqual(self.orderpoint.qty_available_at_source, 70.0)

    def test_orderpoint_without_a_reserve_shows_plain_availability(self):
        self._set_hub_stock(100.0)
        self.orderpoint.invalidate_recordset()
        self.assertEqual(self.orderpoint.qty_available_at_source, 100.0)

    def test_orderpoint_supplied_from_outside_shows_nothing(self):
        """A buy rule sources from a vendor location, which holds no stock."""
        bought = self.env["product.product"].create(
            {"name": "Bought Pump", "is_storable": True}
        )
        orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {
                "warehouse_id": self.hub.id,
                "location_id": self.hub.lot_stock_id.id,
                "product_id": bought.id,
                "product_min_qty": 10.0,
                "product_max_qty": 10.0,
            }
        )
        self.assertFalse(
            orderpoint._get_orderpoint_reserve_source_locations()
            - self.hub.lot_stock_id
        )

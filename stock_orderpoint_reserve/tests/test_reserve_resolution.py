# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from psycopg2.errors import CheckViolation, UniqueViolation

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

from .common import OrderpointReserveCommon


class TestReserveResolution(OrderpointReserveCommon):
    """How a reserve is found, and what it adds up to."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.context_today(cls.env["stock.orderpoint.reserve"])
        cls.reserve_model = cls.env["stock.orderpoint.reserve"]
        cls.shelf = cls.env["stock.location"].create(
            {
                "name": "Shelf 1",
                "location_id": cls.hub.lot_stock_id.id,
                "usage": "internal",
            }
        )

    def _effective(self, location=None, date=None):
        return self.reserve_model._get_effective_reserve(
            self.product, location or self.hub.lot_stock_id, date or self.today
        )

    def test_no_record_reserves_nothing(self):
        self.assertEqual(self._effective(), 0.0)

    def test_records_in_force_add_up(self):
        self._create_reserve(30.0)
        self._create_reserve(20.0, date_stop=self.today + timedelta(days=7))
        self.assertEqual(self._effective(), 50.0)

    def test_parent_location_reserve_covers_children(self):
        self._create_reserve(30.0)
        self.assertEqual(self._effective(location=self.shelf), 30.0)

    def test_child_location_reserve_does_not_cover_parent(self):
        self._create_reserve(30.0, location=self.shelf)
        self.assertEqual(self._effective(), 0.0)
        self.assertEqual(self._effective(location=self.shelf), 30.0)

    def test_nested_reserves_stack(self):
        self._create_reserve(30.0)
        self._create_reserve(20.0, location=self.shelf)
        self.assertEqual(self._effective(location=self.shelf), 50.0)

    def test_out_of_window_reserve_is_ignored(self):
        self._create_reserve(
            30.0,
            date_start=self.today + timedelta(days=1),
            date_stop=self.today + timedelta(days=7),
        )
        self.assertEqual(self._effective(), 0.0)
        self.assertEqual(self._effective(date=self.today + timedelta(days=2)), 30.0)

    def test_archived_reserve_is_ignored(self):
        reserve = self._create_reserve(30.0)
        reserve.active = False
        self.assertEqual(self._effective(), 0.0)

    def test_other_product_is_ignored(self):
        other = self.env["product.product"].create(
            {"name": "Pool Filter", "is_storable": True}
        )
        self._create_reserve(30.0, product=other)
        self.assertEqual(self._effective(), 0.0)

    def test_end_date_before_start_date_is_refused(self):
        with self.assertRaises(ValidationError):
            self._create_reserve(
                30.0,
                date_start=self.today,
                date_stop=self.today - timedelta(days=1),
            )

    # -- open ended windows ------------------------------------------------

    def test_reserve_without_dates_never_lifts(self):
        self._create_reserve(30.0)
        for offset in (-3650, -1, 0, 1, 3650):
            self.assertEqual(
                self._effective(date=self.today + timedelta(days=offset)),
                30.0,
                f"a perpetual reserve should hold {offset} days from today",
            )

    def test_reserve_without_an_end_holds_from_its_start_on(self):
        start = self.today + timedelta(days=5)
        self._create_reserve(30.0, date_start=start)
        self.assertEqual(self._effective(), 0.0)
        self.assertEqual(self._effective(date=start - timedelta(days=1)), 0.0)
        self.assertEqual(self._effective(date=start), 30.0)
        self.assertEqual(self._effective(date=start + timedelta(days=3650)), 30.0)

    def test_reserve_without_a_start_holds_until_its_end(self):
        stop = self.today + timedelta(days=5)
        self._create_reserve(30.0, date_stop=stop)
        self.assertEqual(self._effective(date=self.today - timedelta(days=3650)), 30.0)
        self.assertEqual(self._effective(), 30.0)
        self.assertEqual(self._effective(date=stop), 30.0)
        self.assertEqual(self._effective(date=stop + timedelta(days=1)), 0.0)

    @mute_logger("odoo.sql_db")
    def test_duplicate_perpetual_reserve_is_refused(self):
        """Two open ended records on one shelf are one record, added up."""
        self._create_reserve(30.0)
        with self.assertRaises(UniqueViolation):
            self._create_reserve(20.0)

    # -- breakpoints -------------------------------------------------------

    def _breakpoints(self, days=30):
        return self.reserve_model._get_reserve_breakpoints(
            self.product,
            self.hub.lot_stock_id,
            self.today,
            self.today + timedelta(days=days),
        )

    def test_perpetual_reserve_never_changes(self):
        self._create_reserve(30.0)
        self.assertEqual(self._breakpoints(), [self.today])

    def test_no_reserve_never_changes(self):
        self.assertEqual(self._breakpoints(), [self.today])

    def test_expiry_breaks_on_the_day_after(self):
        """The reserve still holds on its end date; it lifts the day after."""
        stop = self.today + timedelta(days=7)
        self._create_reserve(30.0, date_stop=stop)
        self.assertEqual(self._breakpoints(), [self.today, stop + timedelta(days=1)])

    def test_a_reserve_starting_later_breaks_on_its_start(self):
        start = self.today + timedelta(days=3)
        self._create_reserve(30.0, date_start=start)
        self.assertEqual(self._breakpoints(), [self.today, start])

    def test_changes_beyond_the_window_are_left_out(self):
        self._create_reserve(30.0, date_start=self.today + timedelta(days=90))
        self.assertEqual(self._breakpoints(), [self.today])

    def test_stacked_windows_each_break(self):
        first = self.today + timedelta(days=7)
        second = self.today + timedelta(days=14)
        self._create_reserve(30.0, date_stop=first)
        self._create_reserve(20.0, date_start=second)
        self.assertEqual(
            self._breakpoints(),
            [self.today, first + timedelta(days=1), second],
        )

    @mute_logger("odoo.sql_db")
    def test_zero_quantity_is_refused(self):
        with self.assertRaises(CheckViolation):
            self._create_reserve(0.0)

    def test_available_to_replenish_is_reported(self):
        self._set_hub_stock(100.0)
        self._create_outgoing_move(40.0)
        reserve = self._create_reserve(30.0)
        reserve.invalidate_recordset()
        self.assertEqual(reserve.qty_available, 100.0)
        self.assertEqual(reserve.committed_qty, 40.0)
        self.assertEqual(reserve.qty_available_to_replenish, 30.0)

# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged


@tagged("-at_install", "post_install")
class TestForecastTour(HttpCase):
    """The reserve line has to survive the trip through the browser.

    Everything else about it is checked server side, which says nothing about
    whether the template reaches the page it belongs on.
    """

    def test_reserve_line_is_on_the_forecasted_report(self):
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        product = self.env["product.product"].create(
            {"name": "Reserve Tour Product", "is_storable": True, "is_favorite": True}
        )
        self.env["stock.quant"]._update_available_quantity(
            product, warehouse.lot_stock_id, 100.0
        )
        move = self.env["stock.move"].create(
            {
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": 40.0,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "picking_type_id": warehouse.out_type_id.id,
            }
        )
        move._action_confirm()
        move._action_assign()
        # Ends inside the window the graph draws, so the line has to step:
        # 100 - 40 - 30 = 30 today, 100 - 40 = 60 once the reserve lifts.
        self.env["stock.orderpoint.reserve"].create(
            {
                "product_id": product.id,
                "location_id": warehouse.lot_stock_id.id,
                "quantity": 30.0,
                "date_stop": fields.Date.context_today(product) + timedelta(days=10),
            }
        )
        self.start_tour(
            "/odoo/action-stock.product_template_action_product",
            "stock_orderpoint_reserve_forecast",
            login="admin",
            timeout=180,
        )

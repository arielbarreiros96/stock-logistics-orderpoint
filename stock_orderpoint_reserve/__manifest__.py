# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Stock Orderpoint Reserve",
    "summary": "Keep a floor of on hand stock out of reach of automatic replenishment",
    "version": "19.0.1.0.0",
    "development_status": "Alpha",
    "category": "Inventory",
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
    "author": "Ariel Barreiros, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "depends": ["stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_orderpoint_reserve_views.xml",
        "views/product_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_orderpoint_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_orderpoint_reserve/static/src/**/*.js",
            "stock_orderpoint_reserve/static/src/**/*.xml",
            # Follows core: the graph renderer is only pulled in when a graph
            # is actually drawn, so its patch has to travel with it.
            (
                "remove",
                "stock_orderpoint_reserve/static/src/stock_forecasted/"
                "forecasted_graph.esm.js",
            ),
        ],
        "web.assets_backend_lazy": [
            "stock_orderpoint_reserve/static/src/stock_forecasted/"
            "forecasted_graph.esm.js",
        ],
        "web.assets_tests": [
            "stock_orderpoint_reserve/static/tests/tours/**/*.js",
        ],
    },
    "installable": True,
}

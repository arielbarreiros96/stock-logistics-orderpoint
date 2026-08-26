# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    orderpoint_reserve_count = fields.Integer(
        compute="_compute_orderpoint_reserve_count",
    )

    @api.depends("product_variant_ids.orderpoint_reserve_count")
    def _compute_orderpoint_reserve_count(self):
        for template in self:
            template.orderpoint_reserve_count = sum(
                template.product_variant_ids.mapped("orderpoint_reserve_count")
            )

    def action_open_orderpoint_reserves(self):
        """Open this template's reserves.

        A reserve is held per variant, because stock is. A template with a
        single variant is spared the choice: the variant is defaulted in.
        """
        return self.product_variant_ids.action_open_orderpoint_reserves()

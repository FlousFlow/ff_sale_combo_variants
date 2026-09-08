# -*- coding: utf-8 -*-
# Part of Flous Flow. See LICENSE file for full copyright and licensing details.
"""Ensure generated combo items are protected against accidental SO line edits."""

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    ff_combo_item_is_generated = fields.Boolean(
        compute='_compute_ff_combo_item_is_generated', search='_search_generated',
    )

    @api.depends('combo_item_id')
    def _compute_ff_combo_item_is_generated(self):
        for line in self:
            line.ff_combo_item_is_generated = bool(
                line.combo_item_id.ff_variant_source_id
            )

    def _search_generated(self, operator, value):
        return [
            ('combo_item_id.ff_variant_source_id', 'in' if value else 'not in',
             self.env['ff.variant.source'].search([]).ids),
        ]

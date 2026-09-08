# -*- coding: utf-8 -*-
# Part of Flous Flow. See LICENSE file for full copyright and licensing details.
"""Targeted sync when the template's variant set changes."""

from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model_create_multi
    def create(self, vals_list):
        templates = super().create(vals_list)
        self._sync_sources_for_templates(templates)
        return templates

    def write(self, vals):
        res = super().write(vals)
        if vals.keys() & {'active', 'sale_ok', 'attribute_line_ids'}:
            self._sync_sources_for_templates(self)
        return res

    def _sync_sources_for_templates(self, templates):
        sources = self.env['ff.variant.source'].sudo().search([
            ('product_tmpl_id', 'in', templates.ids), ('auto_sync', '=', True),
        ])
        sources._apply_variant_sync()
        return True

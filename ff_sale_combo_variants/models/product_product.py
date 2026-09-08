# -*- coding: utf-8 -*-
# Part of Flous Flow. See LICENSE file for full copyright and licensing details.
"""Targeted sync triggers on product models (variant / template changes)."""

from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    ff_generated_item_ids = fields.One2many(
        comodel_name='product.combo.item',
        inverse_name='product_id',
        string="Generated Combo Items",
        domain=[('ff_variant_source_id', '!=', False)],
    )
    ff_variant_source_ids = fields.Many2many(
        comodel_name='ff.variant.source',
        relation='ff_variant_source_selected_rel', column1='product_product_id',
        column2='ff_variant_source_id', string="Selected-Variant Sources",
        readonly=True, groups='ff_sale_combo_variants.group_variant_source_user',
    )

    def _ff_sources_for_template(self):
        """All sources whose template covers these products (active or not)."""
        return self.env['ff.variant.source'].sudo().search([
            ('product_tmpl_id', 'in', self.product_tmpl_id.ids),
        ])

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        if any(vals.get('active', True) for vals in vals_list):
            products._ff_sources_for_template().filtered(
                lambda s: s.auto_sync
            )._apply_variant_sync()
        return products

    def write(self, vals):
        res = super().write(vals)
        if vals.keys() & {'active', 'sale_ok', 'product_tmpl_id'}:
            self._ff_sources_for_template().filtered(
                lambda s: s.auto_sync
            )._apply_variant_sync()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_except_generated_combo_items(self):
        sources = self._ff_sources_for_template().filtered(lambda s: s.auto_sync)
        sources._apply_variant_sync()
        return super()._unlink_except_generated_combo_items()

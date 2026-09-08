# -*- coding: utf-8 -*-
# Part of Flous Flow. See LICENSE file for full copyright and licensing details.
"""Extend the combo configurator controller to expose Smart Variant Source info."""

from odoo.http import request, route

from odoo.addons.sale.controllers.combo_configurator import (
    SaleComboConfiguratorController,
)


class FfSaleComboConfiguratorController(SaleComboConfiguratorController):

    @route(
        route='/ff_sale_combo_variants/combo_configurator/get_sources',
        type='jsonrpc', auth='user', readonly=True,
    )
    def ff_combo_configurator_get_sources(self, product_tmpl_id, **kwargs):
        """Return, per combo choice of the combo product, the template groups
        (sources) and the variants each yields. The JS dialog uses this to show
        one card per template instead of one card per variant.
        """
        if not product_tmpl_id:
            return {'combos': []}
        combo_product = request.env['product.template'].sudo().browse(product_tmpl_id)
        sources = request.env['ff.variant.source'].sudo().search([
            ('combo_id', 'in', combo_product.sudo().combo_ids.ids),
            ('active', '=', True),
        ])
        result = {}
        for source in sources:
            eligible = source._get_eligible_variants()
            result.setdefault(source.combo_id.id, []).append({
                'source_id': source.id,
                'product_tmpl_id': source.product_tmpl_id.id,
                'template_name': source.product_tmpl_id.display_name,
                'variant_mode': source.variant_mode,
                'variants': [
                    {'id': v.id, 'display_name': v.display_name}
                    for v in eligible
                ],
            })
        return {
            'combos': [
                {
                    'combo_id': combo_id,
                    'sources': grouped,
                }
                for combo_id, grouped in result.items()
            ],
        }

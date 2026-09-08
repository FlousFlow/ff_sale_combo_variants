# -*- coding: utf-8 -*-
# Part of Flous Flow. See LICENSE file for full copyright and licensing details.
"""Per-variant extra price override for a variant source."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FfVariantPrice(models.Model):
    _name = 'ff.variant.price'
    _description = "Variant Source Extra Price"
    _rec_name = 'product_variant_id'
    _order = 'variant_source_id, id'

    variant_source_id = fields.Many2one(
        comodel_name='ff.variant.source', required=True, index=True,
        ondelete='cascade',
    )
    product_variant_id = fields.Many2one(
        comodel_name='product.product', required=True, index=True,
        check_company=True, ondelete='cascade',
    )
    extra_price = fields.Float(string="Extra Price", default=0.0)
    company_id = fields.Many2one(
        related='variant_source_id.company_id', store=True, index=True,
    )

    _source_variant_uniq = models.Constraint(
        'unique (variant_source_id, product_variant_id)',
        "A variant can only have one price per variant source.",
    )

    @api.constrains('product_variant_id', 'variant_source_id')
    def _check_variant_belongs_to_source_template(self):
        for price in self:
            if (
                price.product_variant_id.product_tmpl_id
                != price.variant_source_id.product_tmpl_id
            ):
                raise ValidationError(_(
                    "The variant must belong to the variant source's product template."
                ))

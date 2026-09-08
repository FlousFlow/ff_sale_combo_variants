# -*- coding: utf-8 -*-
# Part of Flous Flow. See LICENSE file for full copyright and licensing details.
"""Smart Variant Sources tab on the combo choice form + source-first combo support."""

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class ProductCombo(models.Model):
    _inherit = 'product.combo'

    ff_variant_source_ids = fields.One2many(
        comodel_name='ff.variant.source', inverse_name='combo_id',
        string="Smart Variant Sources",
    )
    ff_variant_source_count = fields.Integer(
        compute='_compute_ff_variant_source_count',
    )

    @api.depends('ff_variant_source_ids')
    def _compute_ff_variant_source_count(self):
        for combo in self:
            combo.ff_variant_source_count = len(combo.ff_variant_source_ids)

    @api.constrains('combo_item_ids', 'ff_variant_source_ids')
    def _check_combo_item_ids_not_empty(self):
        """Core demands at least 1 combo item. Relax it when the combo choice
        is powered by Smart Variant Sources: the sync engine materializes the
        items right after the source is saved, so an item-less combo with an
        active source is a valid intermediate state (source-first workflow).

        A brand-new combo (create) may also start empty: the user creates the
        choice first, then adds a Smart Variant Source which fills it. An
        empty, source-less combo only becomes an error once it is written
        again or its items are removed (see write() and item unlink guard).
        """
        for combo in self:
            if combo.combo_item_ids or combo.ff_variant_source_ids:
                continue
            if self.env.context.get('ff_allow_empty_combo'):
                # Create path: defer validation until first real write.
                continue
            raise ValidationError(_(
                "A combo choice must contain at least 1 product."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        # Brand-new combos may be saved empty: the user then configures a
        # Smart Variant Source which materializes the items (source-first UX).
        # (super().with_context(...) recurses infinitely in this build — set
        # the context on the environment instead.)
        self = self.with_context(ff_allow_empty_combo=True)
        combos = super().create(vals_list)
        combos.filtered(
            lambda c: not c.combo_item_ids and c.ff_variant_source_ids
        ).ff_variant_source_ids._apply_variant_sync()
        return combos

    def write(self, vals):
        res = super().write(vals)
        if 'combo_item_ids' in vals or 'ff_variant_source_ids' in vals:
            self.filtered(
                lambda c: not c.combo_item_ids and c.ff_variant_source_ids
            ).ff_variant_source_ids._apply_variant_sync()
        return res

    def action_view_variant_sources(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Smart Variant Sources",
            'res_model': 'ff.variant.source',
            'view_mode': 'list,form',
            'domain': [('combo_id', '=', self.id)],
            'context': {'default_combo_id': self.id},
        }

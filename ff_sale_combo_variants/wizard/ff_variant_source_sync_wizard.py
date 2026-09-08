# -*- coding: utf-8 -*-
# Part of Flous Flow. See LICENSE file for full copyright and licensing details.
"""Manager wizard: sync all variant sources (idempotent)."""

from odoo import fields, models


class FfVariantSourceSyncWizard(models.TransientModel):
    _name = 'ff.variant.source.sync.wizard'
    _description = "Sync All Variant Sources"

    source_count = fields.Integer(
        string="Sources to Sync", readonly=True,
        default=lambda self: self.env['ff.variant.source'].search_count([]),
    )

    def action_sync_all(self):
        self.env['ff.variant.source'].sync_all_sources()
        return {'type': 'ir.actions.act_window_close'}

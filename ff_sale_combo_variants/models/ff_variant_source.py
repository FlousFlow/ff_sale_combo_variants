# -*- coding: utf-8 -*-
# Part of Flous Flow. See LICENSE file for full copyright and licensing details.
"""Smart Variant Sources: template-level variant configuration for combo choices."""

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class FfVariantSource(models.Model):
    _name = 'ff.variant.source'
    _description = "Product Combo Variant Source"
    _order = 'combo_id, sequence, id'
    _check_company_auto = True
    _inherit = ['mail.thread']

    name = fields.Char(
        string="Name", compute='_compute_name', store=True, compute_sudo=True,
    )
    sequence = fields.Integer(default=10, copy=False)
    combo_id = fields.Many2one(
        comodel_name='product.combo', string="Combo Choice",
        required=True, index=True, ondelete='cascade', tracking=True,
        domain="[('company_id', 'in', (company_id, False))]",
    )
    product_tmpl_id = fields.Many2one(
        comodel_name='product.template', string="Product Template",
        required=True, index=True, tracking=True, check_company=True,
        domain="[('type', '!=', 'combo'), ('company_id', 'in', (company_id, False))]",
    )
    company_id = fields.Many2one(
        comodel_name='res.company', required=True, index=True,
        default=lambda self: self.env.company,
    )
    variant_mode = fields.Selection(
        selection=[
            ('single', "Single Variant"),
            ('all', "All Variants"),
            ('selected', "Selected Variants"),
        ],
        string="Variant Mode", required=True, default='single', tracking=True,
    )
    product_variant_id = fields.Many2one(
        comodel_name='product.product', string="Single Variant",
        domain="[('product_tmpl_id', '=', product_tmpl_id), ('company_id', 'in', (company_id, False))]",
        check_company=True,
    )
    selected_variant_ids = fields.Many2many(
        comodel_name='product.product', string="Selected Variants",
        relation='ff_variant_source_selected_rel',
        domain="[('product_tmpl_id', '=', product_tmpl_id), ('company_id', 'in', (company_id, False))]",
        check_company=True,
    )
    auto_sync = fields.Boolean(
        string="Auto Sync", default=True, tracking=True,
        help="Automatically add newly created variants of the template to the "
             "combo choice, and remove archived ones.",
    )
    default_extra_price = fields.Float(
        string="Default Extra Price", default=0.0,
        help="Extra price applied to every generated combo item. Overridden by "
             "per-variant prices when defined.",
    )
    active = fields.Boolean(default=True, tracking=True)

    generated_item_ids = fields.One2many(
        comodel_name='product.combo.item', inverse_name='ff_variant_source_id',
        string="Generated Items", readonly=True,
    )
    price_ids = fields.One2many(
        comodel_name='ff.variant.price', inverse_name='variant_source_id',
        string="Variant Prices",
    )
    generated_item_count = fields.Integer(
        string="Generated Items Count", compute='_compute_generated_item_count',
    )
    eligible_variant_ids = fields.Many2many(
        comodel_name='product.product', string="Eligible Variants",
        compute='_compute_eligible_variant_ids',
    )
    eligible_variant_count = fields.Integer(
        string="Eligible Variants", compute='_compute_eligible_variant_ids',
    )
    is_outdated = fields.Boolean(
        string="Out of Sync", compute='_compute_is_outdated', search='_search_is_outdated',
        help="True when the generated items no longer match the eligible variants.",
    )

    _combo_template_uniq = models.Constraint(
        'unique (combo_id, product_tmpl_id)',
        "A product template can only be configured once per combo choice.",
    )
    _combo_company_uniq = models.Constraint(
        'unique (combo_id, company_id)',
        "A combo choice belongs to a single company.",
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends('combo_id.display_name', 'product_tmpl_id.display_name', 'variant_mode')
    def _compute_name(self):
        mode_labels = dict(self._fields['variant_mode']._description_selection(self.env))
        for source in self:
            mode = mode_labels.get(source.variant_mode, '')
            source.name = f"{source.product_tmpl_id.display_name or '?'} ({mode})"

    @api.depends('generated_item_ids')
    def _compute_generated_item_count(self):
        # _read_group returns many2one groupby keys as recordsets; key by id.
        counts = {
            source.id: count
            for source, count in self.env['product.combo.item']._read_group(
                domain=[('ff_variant_source_id', 'in', self.ids)],
                groupby=['ff_variant_source_id'], aggregates=['__count'],
            )
        }
        for source in self:
            source.generated_item_count = counts.get(source.id, 0)

    @api.depends(
        'product_tmpl_id.product_variant_ids.active',
        'variant_mode', 'product_variant_id.active',
        'selected_variant_ids.active',
    )
    def _compute_eligible_variant_ids(self):
        # Contextual (non-stored) compute: never written, safe without @api.depends.
        for source in self:
            source.eligible_variant_ids = source._get_eligible_variants()
            source.eligible_variant_count = len(source.eligible_variant_ids)

    def _search_is_outdated(self, operator, value):
        # Compute-then-filter: acceptable for a manager-only configuration list.
        matching = self.search([]).filtered(lambda s: s._is_outdated())
        return [('id', 'in' if value else 'not in', matching.ids)]

    def _compute_is_outdated(self):
        for source in self:
            source.is_outdated = source._is_outdated()

    # ------------------------------------------------------------------
    # Eligibility (channel-agnostic — reusable by POS / website later)
    # ------------------------------------------------------------------

    def _get_eligible_variants(self):
        """Return the variants this source yields, following core rules:
        active, sellable, company-matched, and not already covered by a
        manual combo item of the same combo choice.
        """
        self.ensure_one()
        if not self.product_tmpl_id.active:
            return self.env['product.product']

        if self.variant_mode == 'single':
            variants = self.product_variant_id
        elif self.variant_mode == 'all':
            variants = self.product_tmpl_id.product_variant_ids
        else:  # selected
            variants = self.selected_variant_ids

        variants = variants.filtered(
            lambda v: v.active
            and v.sale_ok
            and v.type != 'combo'
        )
        # A variant already referenced by a manual item of this combo must not
        # be duplicated by a generated item (manual wins, core-level uniqueness).
        manual_products = self.env['product.combo.item'].sudo().search([
            ('combo_id', '=', self.combo_id.id),
            ('ff_variant_source_id', '=', False),
            ('product_id', 'in', variants.ids),
        ]).product_id
        return variants - manual_products

    def _is_outdated(self):
        self.ensure_one()
        desired = set(self._get_eligible_variants().ids)
        current = set(self.generated_item_ids.mapped('product_id').ids)
        return desired != current

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('variant_mode', 'product_variant_id')
    def _check_single_variant_set(self):
        for source in self:
            if source.variant_mode == 'single' and not source.product_variant_id:
                raise ValidationError(_(
                    "Select the product variant for sources in 'Single Variant' mode."
                ))

    @api.constrains('variant_mode', 'selected_variant_ids')
    def _check_selected_variants_set(self):
        for source in self:
            if source.variant_mode == 'selected' and not source.selected_variant_ids:
                raise ValidationError(_(
                    "Tick at least one variant for sources in 'Selected Variants' mode."
                ))

    @api.constrains('combo_id', 'product_tmpl_id', 'company_id')
    def _check_combo_company_consistency(self):
        for source in self:
            if source.combo_id.company_id and source.company_id != source.combo_id.company_id:
                raise ValidationError(_(
                    "The variant source must belong to the same company as its combo choice."
                ))

    @api.constrains('product_tmpl_id')
    def _check_tmpl_not_combo(self):
        for source in self:
            if source.product_tmpl_id.type == 'combo':
                raise ValidationError(_("Combo products can't be combo choices."))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        # Initial sync always applies regardless of auto_sync: the source must
        # materialize its generated items immediately. auto_sync governs only
        # future targeted triggers (new/archived variants).
        sources = super().create(vals_list)
        sources._apply_variant_sync()
        return sources

    def write(self, vals):
        res = super().write(vals)
        # Targeted: only re-sync sources whose configuration changed, or whose
        # template changed (the variant triggers are handled in product models).
        if self.env.context.get('ff_skip_sync'):
            return res
        sync_triggers = {
            'variant_mode', 'product_variant_id', 'selected_variant_ids',
            'auto_sync', 'active', 'combo_id', 'product_tmpl_id',
            'default_extra_price',
        }
        if vals.keys() & sync_triggers:
            to_sync = self.filtered(
                lambda s: s.auto_sync or 'auto_sync' in vals
            )
            to_sync._apply_variant_sync()
        return res

    def unlink(self):
        # Generated items are cascade-deleted with the source; check history
        # dependencies first (sale order lines referencing generated items).
        items = self.generated_item_ids
        sale_lines = self.env['sale.order.line'].sudo().with_context(
            active_test=False,
        ).search_count([('combo_item_id', 'in', items.ids)])
        if sale_lines:
            raise UserError(_(
                "You cannot delete variant sources whose generated combo items are"
                " referenced by %s sale order line(s). Deactivate the source"
                " instead to keep historical orders intact.",
                sale_lines,
            ))
        return super().unlink()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_sync_now(self):
        self._apply_variant_sync()
        self.message_post(body=_("Variants synchronized."))

    def action_view_generated_items(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Generated Combo Items"),
            'res_model': 'product.combo.item',
            'view_mode': 'list,form',
            'domain': [('ff_variant_source_id', '=', self.id)],
            'context': {'default_ff_variant_source_id': self.id, 'create': False},
        }

    def action_open_template(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'res_id': self.product_tmpl_id.id,
            'view_mode': 'form',
        }

    # ------------------------------------------------------------------
    # Sync Engine (idempotent)
    # ------------------------------------------------------------------

    def _apply_variant_sync(self):
        """Diff desired vs existing generated items, batched. Idempotent.

        Creates missing generated items and removes generated items whose
        variant is no longer eligible. Manual items are never touched.
        """
        sources = self.filtered(lambda s: s.combo_id and s.product_tmpl_id)
        if not sources:
            return
        Product = self.env['product.product']

        # 1. Compute desired variants per source (single eligibility call per source).
        desired_by_source = {
            source.id: source._get_eligible_variants().ids for source in sources
        }

        # 2. Fetch existing generated products for all sources in one query.
        existing = defaultdict(set)
        for item in self.env['product.combo.item'].search_read(
            domain=[('ff_variant_source_id', 'in', sources.ids)],
            fields=['ff_variant_source_id', 'product_id'],
        ):
            existing[item['ff_variant_source_id'][0]].add(item['product_id'][0])

        # 3. Apply diff per source (creates / unlinks).
        to_create_vals = []
        to_unlink = self.env['product.combo.item']
        for source in sources:
            desired = set(desired_by_source.get(source.id, []))
            current = existing.get(source.id, set())
            missing = Product.browse(desired - current)
            stale = Product.browse(current - desired)
            for variant in missing:
                to_create_vals.append({
                    'combo_id': source.combo_id.id,
                    'product_id': variant.id,
                    'extra_price': source._get_variant_extra_price(variant),
                    'ff_variant_source_id': source.id,
                    'company_id': source.company_id.id,
                })
            if stale:
                to_unlink += self.generated_item_ids.filtered(
                    lambda item, stale_ids=stale.ids: item.product_id.id in stale_ids
                )
        if to_unlink:
            to_unlink.unlink()
        if to_create_vals:
            self.env['product.combo.item'].sudo().create(to_create_vals)
        return True

    def _get_variant_extra_price(self, variant):
        """Variant-specific price wins over the source default."""
        self.ensure_one()
        price = self.env['ff.variant.price'].sudo().search([
            ('variant_source_id', '=', self.id),
            ('product_variant_id', '=', variant.id),
        ], limit=1)
        return price.extra_price if price else self.default_extra_price

    # ------------------------------------------------------------------
    # Service entry points (cron + wizard)
    # ------------------------------------------------------------------

    @api.model
    def _cron_sync_outdated_sources(self):
        """Catch safety net for sources missed by targeted triggers."""
        sources = self.search([('auto_sync', '=', True)])
        outdated = sources.filtered(lambda s: s._is_outdated())
        outdated._apply_variant_sync()
        return True

    @api.model
    def sync_all_sources(self):
        """Manager action: full re-sync of every source (idempotent)."""
        self.search([])._apply_variant_sync()
        return True

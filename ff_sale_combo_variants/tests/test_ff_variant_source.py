# -*- coding: utf-8 -*-
# Part of Flous Flow. See LICENSE file for full copyright and licensing details.
"""Sync engine tests: modes, auto-sync, idempotency, archive, manual isolation."""

import psycopg2

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFfVariantSource(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env['product.product']
        cls.Combo = cls.env['product.combo']
        cls.Source = cls.env['ff.variant.source']

        # Template with one attribute (Size) and 3 values.
        cls.size_attr = cls.env['product.attribute'].create({
            'name': "Size", 'display_type': 'radio', 'create_variant': 'always',
        })
        cls.size_values = cls.env['product.attribute.value'].create([
            {'name': name, 'attribute_id': cls.size_attr.id}
            for name in ("250ml", "330ml", "1L")
        ])
        cls.tmpl = cls.env['product.template'].create({
            'name': "Pepsi",
            'attribute_line_ids': [Command.create({
                'attribute_id': cls.size_attr.id,
                'value_ids': [Command.set(cls.size_values.ids)],
            })],
        })
        cls.variants = cls.tmpl.product_variant_ids

        # Manual item covering the same combo (protection test).
        cls.other_variant = cls.env['product.template'].create({
            'name': "Mineral Water",
        }).product_variant_id
        cls.combo = cls.env['product.combo'].create({
            'name': "Drinks",
            'combo_item_ids': [
                Command.create({'product_id': cls.other_variant.id}),
            ],
        })
        cls.combo_product = cls.env['product.template'].create({
            'name': "Meal", 'type': 'combo',
            'combo_ids': [Command.link(cls.combo.id)],
        })

    # -- Test 1: template without attributes ----------------------------

    def test_template_without_attributes(self):
        plain = self.env['product.template'].create({'name': "Poster"})
        source = self.env['ff.variant.source'].create({
            'combo_id': self.combo.id,
            'product_tmpl_id': plain.id,
            'variant_mode': 'all',
        })
        self.assertEqual(len(source.generated_item_ids), 1)

    # -- Test 2: all variants mode ---------------------------------------

    def test_all_variants_available(self):
        source = self.env['ff.variant.source'].create({
            'combo_id': self.combo.id,
            'product_tmpl_id': self.tmpl.id,
            'variant_mode': 'all',
            'auto_sync': False,
        })
        self.assertEqual(
            source.generated_item_ids.product_id, self.variants,
            "All active variants must be generated as combo items",
        )

    # -- Test 3: selected variants only ----------------------------------

    def test_selected_variants_only(self):
        three = self.variants[:3] if len(self.variants) >= 3 else self.variants
        source = self.env['ff.variant.source'].create({
            'combo_id': self.combo.id,
            'product_tmpl_id': self.tmpl.id,
            'variant_mode': 'selected',
            'selected_variant_ids': [Command.set(three.ids)],
        })
        self.assertEqual(source.generated_item_ids.product_id, three)

    # -- Test 4: new variant auto syncs -----------------------------------

    def test_auto_sync_new_variant(self):
        self.env['ff.variant.source'].create({
            'combo_id': self.combo.id,
            'product_tmpl_id': self.tmpl.id,
            'variant_mode': 'all',
        })
        before = len(self.env['product.combo.item'].search([
            ('ff_variant_source_id', '=', False),
            ('combo_id', '=', self.combo.id),
        ]))
        # Adding a 4th value triggers _create_variant_ids -> targeted sync.
        new_value = self.env['product.attribute.value'].create({
            'name': "500ml", 'attribute_id': self.size_attr.id,
        })
        line = self.tmpl.attribute_line_ids[0]
        line.value_ids = [Command.link(new_value.id)]
        source = self.env['ff.variant.source'].search([
            ('combo_id', '=', self.combo.id),
        ])
        items = self.env['product.combo.item'].search([
            ('ff_variant_source_id', '=', source.id),
        ])
        self.assertEqual(len(items), 4)

    # -- Test 5: idempotency ------------------------------------------------

    def test_sync_twice_no_duplicates(self):
        source = self.env['ff.variant.source'].create({
            'combo_id': self.combo.id,
            'product_tmpl_id': self.tmpl.id,
            'variant_mode': 'all',
        })
        for _ in range(10):
            source.action_sync_now()
        self.assertEqual(
            len(source.generated_item_ids), len(self.tmpl.product_variant_ids)
        )

    # -- Test 6: archive variant -------------------------------------------

    def test_archived_variant_not_available(self):
        source = self.env['ff.variant.source'].create({
            'combo_id': self.combo.id,
            'product_tmpl_id': self.tmpl.id,
            'variant_mode': 'all',
        })
        victim = self.variants[0]
        victim.active = False
        self.assertNotIn(
            victim, source.generated_item_ids.product_id,
            "Archived variant must disappear from generated items",
        )

    # -- Manual isolation (Test 8 core part) ----------------------------------

    def test_manual_item_untouched(self):
        manual_item = self.combo.combo_item_ids.filtered(
            lambda i: not i.ff_variant_source_id
        )
        self.assertTrue(manual_item)
        self.env['ff.variant.source'].create({
            'combo_id': self.combo.id,
            'product_tmpl_id': self.tmpl.id,
            'variant_mode': 'all',
        })
        self.assertTrue(manual_item.exists())

    # -- Duplicate source constraint ------------------------------------------

    def test_duplicate_source_raises(self):
        self.env['ff.variant.source'].create({
            'combo_id': self.combo.id,
            'product_tmpl_id': self.tmpl.id,
            'variant_mode': 'all',
        })
        # SQL-level constraint on create → raw psycopg2 IntegrityError.
        with self.assertRaises(psycopg2.errors.UniqueViolation):
            self.env['ff.variant.source'].create({
                'combo_id': self.combo.id,
                'product_tmpl_id': self.tmpl.id,
                'variant_mode': 'selected',
                'selected_variant_ids': [Command.set(self.variants.ids)],
            })


@tagged('post_install', '-at_install')
class TestSourceFirstCombo(TransactionCase):
    """Source-first workflow: create a combo choice with no items, add a
    Smart Variant Source, and the items materialize automatically. Core's
    'must contain at least 1 product' constraint must relax for sourced combos."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.size_attr = cls.env['product.attribute'].create({
            'name': "SF Size", 'display_type': 'radio', 'create_variant': 'always',
        })
        cls.size_values = cls.env['product.attribute.value'].create([
            {'name': name, 'attribute_id': cls.size_attr.id}
            for name in ("S", "M")
        ])
        cls.tmpl = cls.env['product.template'].create({
            'name': "SF Product",
            'attribute_line_ids': [Command.create({
                'attribute_id': cls.size_attr.id,
                'value_ids': [Command.set(cls.size_values.ids)],
            })],
        })

    def test_sourced_combo_allows_zero_items(self):
        """A combo with 0 items but an active source must be valid."""
        combo = self.env['product.combo'].create({'name': "SF Combo"})
        self.env['ff.variant.source'].create({
            'combo_id': combo.id,
            'product_tmpl_id': self.tmpl.id,
            'variant_mode': 'all',
        })
        # Items were materialized by the source sync:
        self.assertTrue(combo.combo_item_ids)
        # And removing all items while source exists must NOT raise:
        combo.combo_item_ids.unlink()
        self.assertTrue(combo.exists())

    def test_unsourced_combo_still_requires_items(self):
        """Core rule intact for combos without sources."""
        variant = self.tmpl.product_variant_id
        combo = self.env['product.combo'].create({
            'name': "Plain2",
            'combo_item_ids': [Command.create({'product_id': variant.id})],
        })
        # Removing all items from a combo WITHOUT any source must raise the
        # core ValidationError.
        with self.assertRaises(ValidationError):
            combo.combo_item_ids.unlink()

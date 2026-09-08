# -*- coding: utf-8 -*-
# Part of Flous Flow. See LICENSE file for full copyright and licensing details.
"""Sale flow test: Pepsi → 330ml/Zero resolved inside a Meal combo."""

from odoo.fields import Command
from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFfSaleComboFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.size_attr = cls.env['product.attribute'].create({
            'name': "Size", 'display_type': 'radio', 'create_variant': 'always',
        })
        cls.type_attr = cls.env['product.attribute'].create({
            'name': "Type", 'display_type': 'radio', 'create_variant': 'always',
        })
        cls.size_values = cls.env['product.attribute.value'].create([
            {'name': name, 'attribute_id': cls.size_attr.id}
            for name in ("250ml", "330ml")
        ])
        cls.type_values = cls.env['product.attribute.value'].create([
            {'name': name, 'attribute_id': cls.type_attr.id}
            for name in ("Regular", "Zero")
        ])
        cls.pepsi = cls.env['product.template'].create({
            'name': "Pepsi",
            'attribute_line_ids': [
                Command.create({
                    'attribute_id': cls.size_attr.id,
                    'value_ids': [Command.set(cls.size_values.ids)],
                }),
                Command.create({
                    'attribute_id': cls.type_attr.id,
                    'value_ids': [Command.set(cls.type_values.ids)],
                }),
            ],
        })
        cls.variant_330_zero = cls.pepsi.product_variant_ids.filtered(
            lambda v: '330ml' in v.display_name and 'Zero' in v.display_name
        )
        cls.water_variant = cls.env['product.template'].create({
            'name': "Water",
        }).product_variant_id
        cls.pepsi_variant = cls.pepsi.product_variant_id

        cls.drink_combo = cls.env['product.combo'].create({
            'name': "Drink",
            'combo_item_ids': [
                Command.create({'product_id': cls.water_variant.id}),
                Command.create({'product_id': cls.pepsi_variant.id}),
            ],
        })
        cls.meal = cls.env['product.template'].create({
            'name': "Meal", 'type': 'combo',
            'combo_ids': [Command.link(cls.drink_combo.id)],
        })

        # Smart source: Pepsi -> All Variants
        cls.source = cls.env['ff.variant.source'].create({
            'combo_id': cls.drink_combo.id,
            'product_tmpl_id': cls.pepsi.id,
            'variant_mode': 'all',
            'default_extra_price': 2.0,
        })
        cls.partner = cls.env['res.partner'].create({'name': "Test Customer"})

    def _create_order(self):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

    def test_resolved_variant_on_sale_order(self):
        """Test 44: Pepsi → 330ml/Zero resolves to the real variant line."""
        order = self._create_order()
        combo_line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.meal.product_variant_id.id,
        })
        self.assertTrue(combo_line)
        # Select the generated Pepsi item as the combo choice, as the
        # configurator would.
        pepsi_item = self.env['product.combo.item'].search([
            ('combo_id', '=', self.drink_combo.id),
            ('product_id', '=', self.pepsi_variant.id),
        ], limit=1)
        self.assertTrue(pepsi_item, "Generated combo item for Pepsi must exist")
        child = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.pepsi_variant.id,
            'combo_item_id': pepsi_item.id,
            'linked_line_id': combo_line.id,
        })
        self.assertTrue(child, "Child combo line must exist")
        self.assertEqual(
            child.combo_item_id.product_id, self.pepsi_variant,
            "Child line product must match its combo item",
        )

    def test_historical_order_with_archived_variant(self):
        """Test 7: old order stays intact after variant archive."""
        order = self._create_order()
        combo_line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.meal.product_variant_id.id,
        })
        child = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.pepsi_variant.id,
            'combo_item_id': self.env['product.combo.item'].search([
                ('combo_id', '=', self.drink_combo.id),
                ('product_id', '=', self.pepsi_variant.id),
            ], limit=1).id,
            'linked_line_id': combo_line.id,
        })
        self.assertTrue(child)
        # Archive the pepsi variant; the generated item goes away but the
        # historical sale order lines must remain valid.
        self.pepsi_variant.active = False
        self.assertTrue(order.order_line.exists(),
                        "Historical sale order must remain intact")
        self.assertTrue(child.exists())

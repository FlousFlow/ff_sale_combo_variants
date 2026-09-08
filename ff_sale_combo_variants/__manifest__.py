# -*- coding: utf-8 -*-
# Part of Flous Flow. See LICENSE file for full copyright and licensing details.
{
    'name': "Smart Combo Variant Sources",
    'summary': "Template-level variant sources for Combo Products in Sales: "
               "All/Selected Variants, auto sync, hierarchical selection UX",
    'description': """
Smart Combo Variant Sources
===========================
Replace manual per-variant combo items with Product Template level sources:
- Single Variant / All Variants / Selected Variants modes
- Idempotent targeted auto-sync when variants are created or archived
- Hierarchical sales selection: pick template, then attributes, resolved to
  the real product.product via the standard Sale flow
- Zero core modification; existing combos keep working unchanged
    """,
    'author': "Flous Flow",
    'website': "https://flousflow.com",
    'category': 'Sales/Sales',
    'version': '19.0.1.1.0',
    'license': 'LGPL-3',
    'images': [
        'static/description/icon.png',
        'static/description/banner.png',
        'static/description/thumbnail.png',
        'static/description/cover.png',
    ],
    'depends': ['sale_management'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/ff_variant_source_views.xml',
        'views/product_combo_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ff_sale_combo_variants/static/src/combo_configurator_dialog/**/*',
            'ff_sale_combo_variants/static/src/sale_product_field/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}

/** @odoo-module **/

/**
 * Smart Variant Sources: enrich the core ComboConfiguratorDialog with
 * hierarchical template cards. Loaded as a backend asset; the dialog remains
 * fully functional for combos without sources (zero behavior change).
 */

import { ComboConfiguratorDialog } from '@sale/js/combo_configurator_dialog/combo_configurator_dialog';
import { rpc } from '@web/core/network/rpc';
import { patch } from '@web/core/utils/patch';

patch(ComboConfiguratorDialog.prototype, {
    setup() {
        super.setup(...arguments);
        // combo_id -> [{ source_id, product_tmpl_id, template_name, variants }]
        this.state.ffTemplateGroups = {};
        this.state.ffExpandedSourceId = null;
        this._ffLoadTemplateGroups();
    },

    /**
     * Load Smart Variant Source grouping for this combo product.
     * Errors are swallowed: the standard dialog must keep working if the
     * endpoint fails for any reason.
     */
    async _ffLoadTemplateGroups() {
        try {
            const result = await rpc(
                '/ff_sale_combo_variants/combo_configurator/get_sources',
                { product_tmpl_id: this.props.product_tmpl_id },
            );
            for (const comboData of result.combos || []) {
                this.state.ffTemplateGroups[comboData.combo_id] = comboData.sources
                    .filter((source) => source.variants.length > 0);
            }
        } catch {
            this.state.ffTemplateGroups = {};
        }
    },

    /**
     * Return the template groups for a combo (may be empty).
     */
    getFfTemplateGroups(comboId) {
        return this.state.ffTemplateGroups[comboId] || [];
    },

    /**
     * True when at least one source is configured on this combo.
     */
    hasFfSources(comboId) {
        return this.getFfTemplateGroups(comboId).length > 0;
    },

    /**
     * True when this template group is expanded (multi-variant selection).
     */
    isFfTemplateExpanded(sourceId) {
        return this.state.ffExpandedSourceId === sourceId;
    },

    /**
     * Select a template inside a combo:
     * - single-variant template -> select the variant immediately;
     * - multi-variant -> expand the template card to show the variant selector.
     */
    ffSelectTemplate(combo, source) {
        if (source.variants.length === 1) {
            return this.ffSelectVariant(combo, source, source.variants[0].id);
        }
        this.state.ffExpandedSourceId =
            this.state.ffExpandedSourceId === source.source_id ? null : source.source_id;
    },
});

patch(ComboConfiguratorDialog.prototype, {
    /**
     * Select the combo item matching the resolved variant, falling back to the
     * first item if no generated item exists (post-sync this is rare).
     */
    async ffSelectVariant(combo, source, variantId) {
        const comboItem = combo.combo_items.find(
            (item) => item.product && item.product.id === variantId,
        );
        if (comboItem) {
            await this.selectComboItem(combo.id, comboItem);
            return;
        }
        if (combo.combo_items.length) {
            await this.selectComboItem(combo.id, combo.combo_items[0]);
        }
    },
});

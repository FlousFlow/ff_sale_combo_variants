# ff_sale_combo_variants

**Publisher**: Flous Flow — https://flousflow.com

Smart Template-level Variant Sources for Odoo 19 Combo Products (Sales).

Instead of manually adding every product variant as a Combo Choice item, add the
**Product Template** once and choose a Variant Mode:

| Mode | Behavior |
|---|---|
| **Single Variant** | Exactly one variant (classic behavior) |
| **All Variants** | Every active variant of the template becomes a valid choice |
| **Selected Variants** | Only the ticked variants are valid choices |

With **Auto Sync**, newly created variants are added to every combo choice
linked to their template automatically — idempotently, without duplicates.

## Sales UX

When a salesperson adds a combo product to a quotation:

1. Choose the component **Product Template** (e.g. Pepsi, not 24 variants).
2. Choose the **attributes** (Size, Type, RAM, Color…).
3. The system resolves the combination to the real **`product.product`**.
4. Standard Sale flow (delivery, invoicing, COGS) runs unchanged.

## Key Facts

- **No core modification** — model/view/controller inheritance + OWL patch only.
- Existing (manual) combo items are untouched and keep working exactly as before.
- Generated items are read-only, traceable to their source, and removed/added
  idempotently by the sync engine.
- Archiving a variant makes it unavailable for new sales but never breaks
  historical sale orders.
- Multi-company safe (`check_company=True` everywhere).

## Configuration

Menu: **Sales → Configuration → Products → Smart Variant Sources**

- Add a source per (Combo Choice × Product Template).
- Set the Variant Mode, optional extra price, and tick Auto Sync.
- Use **Sync Variants Now** to apply immediately.

Requires *Product Manager* rights to manage sources.

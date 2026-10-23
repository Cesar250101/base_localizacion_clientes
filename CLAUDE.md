@# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this module is

`base_localizacion_clientes` is a cross-cutting localization/customization layer for Method's Chilean Odoo 16 clients. It does not introduce one feature — it patches many core and third-party modules (`base`, `stock`, `product`, `point_of_sale`, `crm`, `account`, `project`, `hr_timesheet`, `sale`, `purchase`, `repair`) listed in `__manifest__.py`. Because of this, a change here can ripple across sales, invoicing, POS, CRM and purchasing simultaneously — check all of `models/`, not just the file that looks relevant.

See [README.md](README.md) for the full functional feature list (already accurate, don't duplicate it here).

## Commands

Run from the server root (`c:\Program Files\Odoo 16\server`), not from this module directory.

```bash
# Update this module only (run after any model/view/data change)
python odoo-bin -c odoo.conf -u base_localizacion_clientes -d <database> --stop-after-init

# Full install (e.g. on a fresh DB) — demo/demo.xml is present but currently empty/commented out
python odoo-bin -c odoo.conf -i base_localizacion_clientes -d <database> --stop-after-init
```

Tests live in `tests/` (`TransactionCase`). Run them against a **clone** of a database, never against a real one:

```bash
python odoo-bin -c odoo.conf -d <clone> -u base_localizacion_clientes --stop-after-init --test-tags /base_localizacion_clientes
```

The purchase-lines Excel import wizard (`wizard/import_purchase_lines_wizard.py`) requires `openpyxl`; it raises a `UserError` at runtime if the library is missing rather than failing on import.

## Architecture

### Plan/Topes (subscription limits) — logic is duplicated in 3 places

`base_localiazcion_clientes.planes_topes` (note: misspelled model name, matches what's actually defined in [models/res_company.py](models/res_company.py) — don't "fix" it without a data migration) defines named plans with `max_dtes` and `max_ventas`. Seed data lives in [data/planes_topes.xml](data/planes_topes.xml): `Inicia`, `Emprende`, `Empresa`, `Empresa PRO`. A company is linked via `res.company.planes_topes_id`.

Enforcement only applies to the `Inicia` and `Emprende` plans (checked by plan **name**, not a flag) and is independently reimplemented in three places, each recomputing month-to-date totals from scratch:
- [models/sale_order.py](models/sale_order.py) `create()` — blocks new sale orders past `max_ventas`.
- [models/account_move.py](models/account_move.py) `create()` — blocks posted invoices past `max_ventas` (Inicia) or `max_dtes` (Inicia/Emprende).
- [models/pos_config.py](models/pos_config.py) `open_ui()` — blocks opening a POS session past the same limits.

When changing limit behavior, update all three. Note `pos_config.py`'s error messages reference `planes_topes_id.max_monto` / `max_dts`, which are not real fields on the model (only `max_ventas`/`max_dtes` exist) — that branch will raise `AttributeError` instead of the intended `UserError` if it's ever hit.

### Multi-company segmentation beyond Odoo's standard company rules

Many models get an explicit `company_id` added on top of (or instead of) Odoo's built-in company security rules: `product.template`, `product.category`, `pos.category`, `res.partner`. The recurring domain pattern is `[('company_id', 'in', [False, current_company.id])]` (e.g. `product_template.py` `_get_company_domain()`), i.e. "global or belongs to my company."

POS categories carry this further into the frontend: [models/pos_session.py](models/pos_session.py) exposes `company_id` to the loaded POS data, and the legacy POS JS module [static/src/js/pos_category_filter.js](static/src/js/pos_category_filter.js) (old `odoo.define`/`Registries` system, not OWL) filters `pos.category` records client-side by the session's company before they're loaded into the POS UI.

### Partner with several companies (`partner_company_ids`, BASELOCCLI-009)

`res.partner.company_id` stays a Many2one (the **main** company; its type, column and default must not change: `res.partner.bank.company_id` is `related='partner_id.company_id'`, `check_company` and core `write` assume a single company). All the contact's companies live in `partner_company_ids` (Many2many, table `res_partner_company_rel`). Empty list = global contact. A literal One2many is not possible (it needs a Many2one inverse on `res.company`).

- Invariant: if `company_id` is set it is in `partner_company_ids`, kept by `res.partner.create`/`write` ([models/res_partner.py](models/res_partner.py)). Changing `company_id` adds the new one and keeps the old; clearing `company_id` (without touching the list) clears the list (global again); removing the main company from a list that keeps others moves `company_id` to the lowest-id company left; emptying the list re-adds `company_id`. The list is not propagated to child contacts.
- Domains (`contacts.action_contacts`, `account.res_partner_action_customer`, filter `company_contacts`, `res.company._sync_contacts_action_domain`, MatchPoint `_matchpoint_find_partner`, `product.supplierinfo.partner_id`, merge wizard duplicates) use `('partner_company_ids', 'in', [company])` and `('partner_company_ids', '=', False)` for global. New code that means "contacts of the company" must do the same, not `company_id`.
- [security/res_partner_rule.xml](security/res_partner_rule.xml) redefines core `base.res_partner_rule` through a `<function>` (`res.partner._update_partner_company_rule`, run on every `-u`; a `<record>` would be ignored because the core record is `noupdate` in `ir_model_data`) so a contact is also visible in each company of the list; `partner_share=False` and `company_id` empty keep their old behaviour.
- Merge wizard unions the companies of the merged contacts into the destination.
- Deliberately still on `company_id` (main company): the GestiOO webhook partner lookup ([controllers/controllers.py](controllers/controllers.py)), `account.move.partner_id` ([views/account_move.xml](views/account_move.xml)) and `account.payment.partner_id` ([models/account_payment.py](models/account_payment.py)). Only `account.move` and `account.payment` (`_check_company_auto`) validate on save that the partner's main company is the document's company; `sale.order`, `purchase.order` and `product.supplierinfo` do not. The webhook stays on `company_id` because the invoice that later comes out of its order (`account.move`) would reject a contact whose main company is another one, even if the company is in its list.
- Install/uninstall: `post_init_hook` (`-i`; migrations only run on `-u`) and migration 0.8 share `hooks.populate_partner_companies`. `uninstall_hook` puts back the core `base.res_partner_rule` domain (otherwise every non-superuser `res.partner` search fails with `Invalid field ... partner_company_ids`) and clears the `partner_company_ids` domain / `company_contacts` default from the two core actions.
- Known behaviours: (a) changing the main company keeps the previous one in the list, so e.g. a portal user created for B while working in company 1 stays visible in both until its tag is removed; (b) a contact with a list `[A, B]` but no main company is still visible in every company through the rule (`company_id` empty), and is only hidden in the actions; (c) the list is not propagated to child contacts.
- Migration [migrations/0.8/post-migrate.py](migrations/0.8/post-migrate.py) copies each `company_id` into the list (idempotent).

### `allowed_company_ids` context convention

Several places read `self.env.context.get('allowed_company_ids')[0]` instead of `self.env.company` to determine "the active company," notably [models/crm_lead.py](models/crm_lead.py) (forces new/updated leads onto the first CRM stage configured for that company), [models/account_payment.py](models/account_payment.py) `_compute_available_journal_ids`, and [models/res_config_settings.py](models/res_config_settings.py) `set_values`. This assumes a single selected company in context and will raise/behave oddly if `allowed_company_ids` is empty — follow this same convention if extending company-scoped logic here rather than mixing in `self.env.company`.

### GestiOO integration (external workshop-management system)

[controllers/controllers.py](controllers/controllers.py) exposes a public, token-authenticated webhook at `/base_localizacion_clientes/gestioo`. Auth is a per-company token (`res.company.token_gestioo`, toggled by `integrar_gestioo`, configured via [models/res_config_settings.py](models/res_config_settings.py)); the webhook URL itself is computed on `res.company` (`url_webhook_gestioo`).

The handler ingests a GestiOO "orden" JSON payload and upserts, in order: `res.partner` (matched by `gestioo_id`, falling back to `vat`, else created), `res.users` (matched by `gestioo_id`, falling back to name match, else created with `base.group_user`), `sale.order` (deduped by `gestioo_id`), and `sale.order.line` per product (matched by `gestioo_id` → `default_code` → `name`, else created with a hardcoded 19% sale tax lookup). All cross-model linkage to GestiOO records goes through a `gestioo_id` char field added to `res.partner`, `res.users`, `product.product`, and `sale.order`.

### Purchase order Excel line import

[wizard/import_purchase_lines_wizard.py](wizard/import_purchase_lines_wizard.py) is a `TransientModel` wizard opened from `purchase.order` via `action_open_import_lines_wizard()` ([models/purchase_order.py](models/purchase_order.py)). It reads an uploaded `.xlsx` (columns: SKU, Cantidad, Precio starting row 2), resolves products by `default_code`, and creates `purchase.order.line` records — collecting all row errors before raising a single `UserError` rather than failing on the first bad row. The downloadable template is served as a static file at `/base_localizacion_clientes/static/archivos/ImportPOL.xlsx`, separate from the `archivos/`-prefixed working copy used elsewhere.

### Custom account grouping

`account.group.custom` ([models/account_group.py](models/account_group.py)) is a parallel, hierarchical (`_parent_store`) chart-of-accounts grouping with a recursive computed `display_name` (`Parent / Child`) and an M2M to `account.account`. This is independent from Odoo's built-in `account.group` model — don't conflate the two when navigating account-grouping code.

### Sale order report override

[report/report_saleorder_document.xml](report/report_saleorder_document.xml) inherits `sale.report_saleorder_document` to restructure the customer address block into a table, add two always-visible product columns (SKU = `default_code`, Producto = `line.name`), and relabel "Untaxed Amount" to "Monto Neto." See the README's table for the full behavior list — treat that XML as the single source of truth for layout details, not the README.

The base `sale.report_saleorder_document` view itself is **not identical across databases** — in `clicksale` it was hand-edited (outside any module) to add an extra `th_producto`/`td_product_id` column (`line.product_id.name`) ahead of the description column; other databases (`emsin`, `taller4`, `PosSuiteDemo`, `asvetec`) use the vanilla core structure. The inert `report_saleorder_document_inherit_localizacion_std` template below is a leftover attempt at handling this kind of per-database divergence — its comment references a `_desactivar_report_std_sin_anclas()` function that was never implemented, so it's permanently `active="False"` everywhere; don't rely on it as precedent.

The **working** pattern for this divergence is `report_saleorder_document_inherit_localizacion_legacy_producto` (also `active="False"` in XML) plus [models/ir_ui_view.py](models/ir_ui_view.py) `_register_hook()`, which runs on every registry load, inspects `sale.report_saleorder_document`'s raw `arch_db` for the `th_producto`/`td_product_id` node names, and flips that template's `active` flag accordingly. If you add another xpath that only applies to a subset of databases, follow this hook-based detection pattern rather than a hardcoded always-on xpath — an unconditional xpath against a node that doesn't exist in the base view breaks that entire view (and therefore all sale order/quotation printing) on every database missing the node.

### Partner merge override

[wizard/base_partner_merge.py](wizard/base_partner_merge.py) inherits the core `base.partner.merge.automatic.wizard` to scope duplicate detection to the active company (`self.env.company.id`, partners whose `partner_company_ids` contain it or are empty) and to union the companies of the merged contacts into the destination and to let admins bypass the core 3-contact merge safety check.

# -*- coding: utf-8 -*-

from odoo import models
from odoo.exceptions import UserError
from odoo.fields import Command


class BasePartnerMergeAutomaticWizard(models.TransientModel):
    _inherit = 'base.partner.merge.automatic.wizard'

    def _merge(self, partner_ids, dst_partner=None, extra_checks=True):
        # Se omite la validación del límite de 3 contactos
        if self.env.is_admin():
            extra_checks = False

        Partner = self.env['res.partner']
        partner_ids = Partner.browse(partner_ids).exists()
        if len(partner_ids) < 2:
            return

        # check if the list of partners to merge contains child/parent relation
        child_ids = self.env['res.partner']
        for partner_id in partner_ids:
            child_ids |= Partner.search([('id', 'child_of', [partner_id.id])]) - partner_id
        if partner_ids & child_ids:
            raise UserError(self.env._("You cannot merge a contact with one of his parent."))

        if extra_checks and len(set(partner.email for partner in partner_ids)) > 1:
            raise UserError(self.env._("All contacts must have the same email. Only the Administrator can merge contacts with different emails."))

        if dst_partner and dst_partner in partner_ids:
            src_partners = partner_ids - dst_partner
        else:
            ordered_partners = self._get_ordered_partner(partner_ids.ids)
            dst_partner = ordered_partners[-1]
            src_partners = ordered_partners[:-1]

        if dst_partner.company_id:
            partner_ids.mapped('user_ids').sudo().write({
                'company_ids': [Command.link(dst_partner.company_id.id)],
                'company_id': dst_partner.company_id.id,
            })

        self._update_foreign_keys(src_partners, dst_partner)
        self._update_reference_fields(src_partners, dst_partner)
        self._update_values(src_partners, dst_partner)

        self.env.add_to_compute(dst_partner._fields['partner_share'], dst_partner)
        self._log_merge_operation(src_partners, dst_partner)
        src_partners.unlink()

    def _get_ordered_partner(self, partner_ids):
        # El destino es el partner con el ID más bajo (el más antiguo en la base de datos)
        return self.env['res.partner'].browse(partner_ids).sorted(key=lambda p: p.id, reverse=True)

    def action_start_manual_process(self):
        self.ensure_one()
        groups = self._compute_selected_groupby()
        query = self._generate_query(groups, self.maximum_group)
        self._process_query_by_company(query)
        return self._action_next_screen()

    def _process_query_by_company(self, query):
        """Como _process_query pero restringe los duplicados a la company_id activa."""
        self.ensure_one()
        model_mapping = self._compute_models()
        company_id = self.env.company.id

        self._cr.execute(query)

        counter = 0
        for _, aggr_ids in self._cr.fetchall():
            # Filtrar solo los partners de la compañía activa dentro del grupo
            partners = self.env['res.partner'].search([
                ('id', 'in', aggr_ids),
                '|',
                ('company_id', '=', company_id),
                ('company_id', '=', False),
            ])
            if len(partners) < 2:
                continue

            if model_mapping and self._partner_use_in(partners.ids, model_mapping):
                continue

            self.env['base.partner.merge.line'].create({
                'wizard_id': self.id,
                'min_id': min(partners.ids),
                'aggr_ids': partners.ids,
            })
            counter += 1

        self.write({
            'state': 'selection',
            'number_group': counter,
        })

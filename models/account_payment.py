# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date, formatLang


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    payment_date = fields.Date(string='Payment Date')
    journal_id = fields.Many2one(
        comodel_name='account.journal', string='Journal', required=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company    _id', '=', company_id)]")   

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Customer/Vendor",
        store=True, readonly=False, ondelete='restrict',
        compute='_compute_partner_id',
        domain="['&', '|', ('parent_id', '=', False), ('is_company', '=', True), ('company_id', 'in', [allowed_company_ids[0], False])]",
        tracking=True,
        check_company=True)
    
    @api.depends('payment_type')
    def _compute_available_journal_ids(self):
        """
        Get all journals having at least one payment method for inbound/outbound depending on the payment_type.
        """
        company=self.env.context.get('allowed_company_ids',False)[0]
        company=self.env['res.company'].search([('id','=',company)])

        journals = self.env['account.journal'].search([
            ('company_id', 'in', company.ids), ('type', 'in', ('bank', 'cash'))
        ])
        self.company_id=company.id
        for pay in self:
            if pay.payment_type == 'inbound':
                pay.available_journal_ids = journals.filtered(
                    lambda j: j.company_id == pay.company_id and j.inbound_payment_method_line_ids.ids != []
                )
            else:
                pay.available_journal_ids = journals.filtered(
                    lambda j: j.company_id == pay.company_id and j.outbound_payment_method_line_ids.ids != []
                )    
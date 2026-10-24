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
        domain="['&', '|', ('parent_id', '=', False), ('is_company', '=', True), '|', ('partner_company_ids', 'in', [allowed_company_ids[0]]), ('partner_company_ids', '=', False)]",
        tracking=True,
        check_company=True)

    def _check_company(self, fnames=None):
        """El contacto del pago es válido si la compañía del pago está en
        partner_company_ids (BASELOCCLI-009/010), no solo si es su compañía principal.

        El core exige partner.company_id <= payment.company_id y rechaza a un
        contacto cuya principal es otra compañía aunque tenga a esta en su lista.
        Solo cambia `partner_id`; el resto de campos va a super(). Si el contacto no
        tiene la compañía del pago, en vez de dar el error del core se le agrega a
        `partner_company_ids`.
        """
        if fnames is None:
            fnames = list(self._fields)
        super()._check_company([name for name in fnames if name != 'partner_id'])
        if 'partner_id' in fnames:
            self.env['res.partner']._link_document_companies(self)

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
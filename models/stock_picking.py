# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    invoice_id = fields.Char(
        string='N° Factura',
        compute='_compute_invoice_id',
    )

    @api.depends('origin')
    def _compute_invoice_id(self):
        for picking in self:
            invoice = self.env['account.move'].search(
                [('invoice_origin', '=', picking.origin)],
                limit=1,
            )
            picking.invoice_id = invoice.sii_document_number

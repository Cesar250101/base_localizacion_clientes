# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    store_original_partner_name = fields.Boolean(
        related='company_id.store_original_partner_name',
        readonly=False,
        string='Conservar nombre original del contacto',
    )

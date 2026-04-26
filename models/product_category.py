# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ProductCategory(models.Model):
    _inherit = 'product.category'

    def _get_default_company_id(self):
        return self.env.company.id

    company_id = fields.Many2one(comodel_name='res.company', 
                                 default=_get_default_company_id, 
                                 string='Compañía')

    
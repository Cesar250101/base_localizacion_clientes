# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ProductCategory(models.Model):
    _inherit = 'pos.category'

    def _get_default_company_id(self):
        return self.env.company.id

    company_id = fields.Many2one(comodel_name='res.company', 
                                 default=_get_default_company_id, 
                                 string='Compañía')
    
    parent_id = fields.Many2one(
        'pos.category',
        string='Parent Category',
        index=True,
        domain="[('company_id', '=', company_id)]"
    )
    
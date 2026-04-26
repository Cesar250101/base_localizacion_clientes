# -*- coding: utf-8 -*-

from odoo import models

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_pos_category(self):
        result = super()._loader_params_pos_category()
        result['search_params']['fields'].append('company_id')
        return result

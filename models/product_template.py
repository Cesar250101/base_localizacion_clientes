import itertools
import logging
from collections import defaultdict

from odoo import api, fields, models, tools, _, SUPERUSER_ID
from odoo.exceptions import ValidationError, RedirectWarning, UserError
from odoo.models import PREFETCH_MAX
from odoo.osv import expression
from odoo.tools import format_amount

_logger = logging.getLogger(__name__)

class ProductCategory(models.Model):
    _inherit = 'product.template'


    company_id = fields.Many2one(
        comodel_name='res.company',string= 'Company', index=True,default=lambda self: self.env.company)
        
    @tools.ormcache()
    def _get_default_category_id(self):
        # Deletion forbidden (at least through unlink)
        return self.env.ref('product.product_category_all')
    
    categ_id = fields.Many2one(comodel_name='product.category', 
                               string='Product Category',
                                change_default=True, 
                                default=_get_default_category_id, 
                                group_expand='_read_group_categ_id',
                                required=True,
                                domain=lambda self: self._get_company_domain())
    
    def _get_company_domain(self):
        # Obtener la compañía actual del usuario
        current_company = self.env.company
        # Retornar el dominio para filtrar por la compañía actual
        return [('company_id', 'in', [False,current_company.id])]

    def _construct_tax_string(self, price):
        if not self:
            return ' '
        currency = self.currency_id
        if not currency:
            currency = self.env.company.currency_id
        res = self.taxes_id.filtered(lambda t: t.company_id == self.env.company).compute_all(
            price, product=self, partner=self.env['res.partner']
        )
        joined = []
        included = res['total_included']
        if currency.compare_amounts(included, price):
            joined.append(_('%s Incl. Taxes', format_amount(self.env, included, currency)))
        excluded = res['total_excluded']
        if currency.compare_amounts(excluded, price):
            joined.append(_('%s Excl. Taxes', format_amount(self.env, excluded, currency)))
        if joined:
            tax_string = f"(= {', '.join(joined)})"
        else:
            tax_string = " "
        return tax_string
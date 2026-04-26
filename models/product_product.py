# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import timedelta, time
from odoo import fields, models, _, api
from odoo.tools.float_utils import float_round

class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.depends('lst_price', 'product_tmpl_id', 'taxes_id')
    @api.depends_context('company')
    def _compute_tax_string(self):
        for record in self:
            if record.product_tmpl_id:
                record.tax_string = record.product_tmpl_id._construct_tax_string(record.lst_price)
            else:
                record.tax_string = ' '

    sales_count_store = fields.Float(compute='_compute_sales_count_store', string='Sold', digits='Product Unit of Measure',store=True)
    qty_available = fields.Float(
        'Quantity On Hand', compute='_compute_quantities', search='_search_qty_available',
        digits='Product Unit of Measure', compute_sudo=False,store=True,
        help="Current quantity of products.\n"
             "In a context with a single Stock Location, this includes "
             "goods stored at this Location, or any of its children.\n"
             "In a context with a single Warehouse, this includes "
             "goods stored in the Stock Location of this Warehouse, or any "
             "of its children.\n"
             "stored in the Stock Location of the Warehouse of this Shop, "
             "or any of its children.\n"
             "Otherwise, this includes goods stored in any Stock Location "
             "with 'internal' type.")
    gestioo_id = fields.Char(string='GestiOO ID', help='ID del producto en GestiOO')
            
    @api.depends('sales_count')
    def _compute_sales_count_store(self):
        r = {}
        self.sales_count_store = 0
        if not self.user_has_groups('sales_team.group_sale_salesman'):
            return r
        date_from = fields.Datetime.to_string(fields.datetime.combine(fields.datetime.now() - timedelta(days=365),
                                                                      time.min))

        done_states = self.env['sale.report']._get_done_states()

        domain = [
            ('state', 'in', done_states),
            ('product_id', 'in', self.ids),
            ('date', '>=', date_from),
        ]
        for group in self.env['sale.report']._read_group(domain, ['product_id', 'product_uom_qty'], ['product_id']):
            r[group['product_id'][0]] = group['product_uom_qty']
        for product in self:
            if not product.id:
                product.sales_count_store = 0.0
                continue
            product.sales_count_store = float_round(r.get(product.id, 0), precision_rounding=product.uom_id.rounding)
        return r

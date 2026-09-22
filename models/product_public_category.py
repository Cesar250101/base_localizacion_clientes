# -*- coding: utf-8 -*-

from odoo import models, fields


class ProductPublicCategory(models.Model):
    _inherit = 'product.public.category'

    product_count = fields.Integer(
        string='Cantidad de productos',
        compute='_compute_product_count',
        help='Productos del sitio web (product.template) que tienen esta categoría '
             'asignada directamente en public_categ_ids. No incluye productos de '
             'subcategorías.',
    )

    def _compute_product_count(self):
        read_group_res = self.env['product.template'].read_group(
            [('public_categ_ids', 'in', self.ids)],
            ['public_categ_ids'], ['public_categ_ids'],
        )
        group_data = dict(
            (data['public_categ_ids'][0], data['public_categ_ids_count'])
            for data in read_group_res
        )
        for categ in self:
            categ.product_count = group_data.get(categ.id, 0)

    def action_view_products(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'website_sale.product_template_action_website')
        action['domain'] = [('public_categ_ids', 'in', self.id)]
        action['context'] = dict(
            action.get('context') or {},
            default_public_categ_ids=[(4, self.id)],
        )
        return action

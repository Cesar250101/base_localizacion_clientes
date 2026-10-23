# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductSupplierInfo(models.Model):
    _inherit = 'product.supplierinfo'

    partner_id = fields.Many2one(
        'res.partner',
        'Vendor',
        ondelete='cascade',
        required=True,
        check_company=True,
        # Contactos de la compañía de la línea: la tienen en partner_company_ids
        # (BASELOCCLI-009); sin compañía, los globales. product.supplierinfo no
        # valida la compañía del contacto al guardar (sin _check_company_auto).
        domain="[('partner_company_ids', '=', company_id)]"
    )
    
    product_id = fields.Many2one(
        'product.product',
        'Product Variant',
        check_company=True,
        # domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        domain="[('company_id', '=', company_id)]",
        help="If not set, the vendor price will apply to all variants of this product."
    )

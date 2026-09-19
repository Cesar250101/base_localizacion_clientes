from odoo import models, fields, api,SUPERUSER_ID
from odoo.exceptions import UserError


class Users(models.Model):
    _inherit = 'res.users'

    gestioo_id = fields.Char(string='GestiOO ID', help='ID del cliente en GestiOO')

    # BASELOCCLI-003/004: pestaña "Funcionalidades de Compras" condicionada al
    # interruptor maestro de res.company (ver models/res_company.py).
    activar_funcionalidades_compras_method = fields.Boolean(
        related='company_id.activar_funcionalidades_compras_method',
        readonly=True,
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación de Inventario',
        domain="[('usage', '=', 'internal')]",
    )
    pos_config_id = fields.Many2one(
        'pos.config',
        string='Punto de Venta / Caja',
    )

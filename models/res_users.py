from odoo import models, fields, api,SUPERUSER_ID
from odoo.exceptions import UserError


class Users(models.Model):
    _inherit = 'res.users'

    gestioo_id = fields.Char(string='GestiOO ID', help='ID del cliente en GestiOO')    

from odoo import models, fields, api

class AccountGroupCustom(models.Model):
    _name = 'account.group.custom'
    _description = 'Agrupación de Cuentas Personalizada'
    _parent_store = True
    _rec_name = 'display_name'

    code = fields.Char(string="Código")
    name = fields.Char(string="Nombre", required=True)
    parent_path = fields.Char(index=True)
    parent_id = fields.Many2one('account.group.custom', string='Grupo Padre', index=True, ondelete='cascade')
    child_ids = fields.One2many('account.group.custom', 'parent_id', string='Grupos Hijos')
    account_ids = fields.Many2many('account.account', string='Cuentas')
    
    display_name = fields.Char(string='Nombre Completo', compute='_compute_display_name', recursive=True, store=True)

    @api.depends('name', 'parent_id.display_name')
    def _compute_display_name(self):
        for group in self:
            if group.parent_id:
                group.display_name = f"{group.parent_id.display_name} / {group.name}"
            else:
                group.display_name = group.name

class AccountAccount(models.Model):
    _inherit = 'account.account'
    
    group_custom_ids = fields.Many2many('account.group.custom', string='Grupos Personalizados')

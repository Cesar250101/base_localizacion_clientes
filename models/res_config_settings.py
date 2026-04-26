from odoo import api, fields, models
from odoo.exceptions import UserError



class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    integra_gestioo = fields.Boolean(string="Integrar con Gestioo", default=False, help="Permite la integración con el sistema Gestioo para la gestión de un taller.")
    token_gestioo = fields.Char(string='Token de Gestioo')

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        res.update({
            'integra_gestioo': IrConfigParam.get_param('base_localizacion_clientes.integra_gestioo', default=''),
            'token_gestioo': IrConfigParam.get_param('base_localizacion_clientes.token_gestioo', default=''),
        })
        return res

    def set_values(self):
        company=self.env.context.get('allowed_company_ids',False)[0]
        company=self.env['res.company'].search([('id','=',company)])
        company.token_gestioo=self.token_gestioo
        super(ResConfigSettings, self).set_values()
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        IrConfigParam.set_param('base_localizacion_clientes.integra_gestioo', self.integra_gestioo or '')
        IrConfigParam.set_param('base_localizacion_clientes.token_gestioo', self.token_gestioo or '')
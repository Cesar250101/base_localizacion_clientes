from pyparsing import line
from odoo import api, exceptions, fields, models, _
from odoo.tools import pycompat
from datetime import datetime, timedelta
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning


class AccountMove(models.Model):
    _inherit = 'account.move'


    invoice_origin = fields.Char(
        string='Origin',
        tracking=True,
        readonly=False,
        help="El(los) documento(s) que generaron la factura.",
    )

    
    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.today()
        first_day = today.replace(day=1)
        last_day = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        domain = [
            ('create_date', '>=', first_day),
            ('create_date', '<=', last_day),
            ('state','=','posted'),
            ('move_type','in',['out_invoice','out_refund','in_invoice','in_refund'])
        ]

        dtes = self.env['account.move'].search(domain)
        count= len(dtes) if dtes else 0,
        amount= sum(dtes.mapped('amount_total')) if dtes else 0,

        if self.env.company.planes_topes_id:
            if self.env.company.planes_topes_id.name in ["Inicia", "Emprende"]:
                if self.env.company.planes_topes_id.name=="Inicia":
                    if amount[0]>self.env.company.planes_topes_id.max_ventas or count[0]>self.env.company.planes_topes_id.max_dtes:
                        raise UserError(
                            'No puede crear una nueva orden ya que ha alcanzado el límite de ' + str(self.env.company.planes_topes_id.max_ventas) + ' de pesos mensual de su plan o ha alcanzado el limite de '
                            + str(self.env.company.planes_topes_id.max_dtes) + ' dtes mensual .Contactese con ventas@method.cl o al telefono +56 9 4233 8955 para actualizar tu plan!'
                        )
                    else:
                        return super().create(vals_list)
                else:
                    if count[0]>self.env.company.planes_topes_id.max_dtes:
                        raise UserError(
                            'No puede crear una nueva factura ya que ha alcanzado el límite de %s nro de dtes de su plan' %
                            self.env.company.planes_topes_id.max_dtes + ' .Contactese con ventas@method.cl o al telefono +56 9 4233 8955 para actualizar tu plan!'
                        )
                    else:
                        return super().create(vals_list)

            else:
                return super().create(vals_list)
        else:
            return super().create(vals_list)
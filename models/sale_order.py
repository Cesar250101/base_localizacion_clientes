from pyparsing import line
from odoo import api, exceptions, fields, models, _
from odoo.tools import pycompat
from datetime import datetime, timedelta
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    gestioo_id = fields.Char(string='GestiOO ID', help='ID de la orden de venta en GestiOO')

    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.today()
        first_day = today.replace(day=1)
        last_day = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        domain = [
            ('date_order', '>=', first_day),
            ('date_order', '<=', last_day),
            ('state','!=','draft')
        ]

        total = sum(order.amount_total for order in self.env['sale.order'].search(domain))
        if self.env.company.planes_topes_id:
            if self.env.company.planes_topes_id.name in["Inicia","Emprende"]:
                if total>self.env.company.planes_topes_id.max_ventas:
                    raise UserError(
                        'No puede crear una nueva orden ya que ha alcanzado el límite de %s de pesos mensual de su plan' %
                        self.env.company.planes_topes_id.max_ventas + ' .Contactese con ventas@method.cl o al telefono +56 9 4233 8955 para actualizar tu plan!'
                    )

                else:
                    return super().create(vals_list)
            else:
                return super().create(vals_list)
        else:
            return super().create(vals_list)


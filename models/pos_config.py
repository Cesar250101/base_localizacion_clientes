from uuid import uuid4
import pytz
from odoo import api, fields, models, tools, _
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning
from datetime import datetime, timedelta

class PosConfig(models.Model):
    _inherit = 'pos.config'

    # stock_location_id = fields.Many2one(
    #     'stock.location', 'Stock Location', required=True,
    #     domain=[('usage', '=', 'internal')])    



    def open_ui(self):
        today = fields.Date.today()
        first_day = today.replace(day=1)
        last_day = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        domain = [
            ('date_order', '>=', first_day),
            ('date_order', '<=', last_day),
        ]
        
        orders = self.env['pos.order'].search(domain)
        count= len(orders),
        amount= sum(orders.mapped('amount_total')),
        orders= orders,

        domain.append(('document_class_id','!=',False))
        dtes=self.env['pos.order'].search(domain)
        count_dtes=len(dtes)
        if self.env.company.planes_topes_id.name in["Inicia","Emprende"]:
            if self.env.company.planes_topes_id.name =="Inicia":
                if self.env.company.planes_topes_id.max_ventas>=amount[0] and self.env.company.planes_topes_id.max_dtes>=count_dtes:
                    return super().open_ui()
                else:
                    raise UserError(
                        'No puede crear una nueva orden ya que ha alcanzado el límite de %s de pesos de su plan' %
                        self.env.company.planes_topes_id.max_monto + ' .Contactese con ventas@method.cl o al telefono +56 9 4233 8955 para actualizar tu plan!'
                    )
            else:
                if self.env.company.planes_topes_id.max_dtes>=count_dtes:
                    return super().open_ui()
                else:
                    raise UserError(
                        'No puede abrir una nueva sesión ya que ha alcanzado el limite de dtes %s mensual' %
                        self.env.company.planes_topes_id.max_dts + ' .Contactese con ventas@method.cl o al telefono +56 9 4233 8955 para actualizar tu plan!'
                    )

        else:
            return super().open_ui()



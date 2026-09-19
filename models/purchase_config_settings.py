# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettingsPurchaseMethod(models.TransientModel):
    _inherit = "res.config.settings"

    # Interruptor maestro de funcionalidades de Compras Method (ver el campo
    # equivalente en models/res_company.py). Expuesto como related para que
    # Ajustes lo persista automáticamente en la compañía activa, sin
    # get_values/set_values manuales.
    activar_funcionalidades_compras_method = fields.Boolean(
        related='company_id.activar_funcionalidades_compras_method',
        string='Activar funcionalidades de Compras (Method)',
        readonly=False,
        help='Interruptor maestro: al activarlo se muestran las funcionalidades '
             'y campos de compras que Method desarrolle desde ahora en este '
             'módulo. En falso, esas funcionalidades permanecen ocultas.',
    )

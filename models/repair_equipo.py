# -*- coding: utf-8 -*-

from odoo import fields, models


class RepairEquipo(models.Model):
    _name = 'emsin.equipos'
    _rec_name = 'name'
    _description = 'Equipos de clientes'

    name = fields.Char(string='Nombre', required=True)
    marca = fields.Char(string='Marca', required=False)
    modelo = fields.Char(string='Modelo', required=False)
    patente = fields.Char(string='Patente', required=False)
    nro_serie = fields.Char(string='Serie/Nro. Interno', required=False)
    hrs_km = fields.Char(string='Horas/Kilometros', required=False)
    partner_id = fields.Many2one(comodel_name='res.partner', string='Cliente', required=True)

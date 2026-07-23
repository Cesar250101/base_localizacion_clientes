# -*- coding: utf-8 -*-

from odoo import api, fields, models


class RepairConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    repair_config_id = fields.Many2one(
        'repair.config',
        compute='_compute_repair_config_id',
    )
    hide_repair_description = fields.Boolean(
        string='Ocultar descripción de la reparación',
        related='repair_config_id.hide_repair_description',
        readonly=False,
    )
    show_repair_usage_hours = fields.Boolean(
        string='Mostrar horas de uso de la unidad o equipo',
        related='repair_config_id.show_repair_usage_hours',
        readonly=False,
    )
    integrate_fleet = fields.Boolean(
        string='Integrar con Flota',
        related='repair_config_id.integrate_fleet',
        readonly=False,
    )
    require_patente = fields.Boolean(
        string='Solicitar patente',
        related='repair_config_id.require_patente',
        readonly=False,
    )
    integrate_emsin_equipos = fields.Boolean(
        string='Integrar equipo del cliente',
        related='repair_config_id.integrate_emsin_equipos',
        readonly=False,
    )

    @api.depends('company_id')
    def _compute_repair_config_id(self):
        RepairConfig = self.env['repair.config'].sudo()
        for settings in self:
            settings.repair_config_id = RepairConfig.get_company_config(
                settings.company_id,
            )

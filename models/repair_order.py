# -*- coding: utf-8 -*-

from odoo import api, fields, models


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    def _get_default_company_id(self):
        return self.env.company.id

    patente = fields.Char(string='Patente', required=True)
    es_taller = fields.Boolean(string='Es Taller', related='company_id.es_taller')
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=_get_default_company_id,
    )
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    fecha_rma = fields.Date(
        string='Fecha RMA',
        default=fields.Date.context_today,
    )
    usage_hours = fields.Float(string='Horas de uso')
    fleet_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehículo',
        check_company=True,
    )
    hide_repair_description = fields.Boolean(
        compute='_compute_repair_configuration',
    )
    show_repair_usage_hours = fields.Boolean(
        compute='_compute_repair_configuration',
    )
    show_repair_fleet_vehicle = fields.Boolean(
        compute='_compute_repair_configuration',
    )

    @api.depends('company_id')
    def _compute_repair_configuration(self):
        configs = {}
        RepairConfig = self.env['repair.config'].sudo()
        for repair in self:
            company_id = repair.company_id.id
            if company_id not in configs:
                configs[company_id] = RepairConfig.search(
                    [('company_id', '=', company_id)],
                    limit=1,
                )
            config = configs[company_id]
            repair.hide_repair_description = config.hide_repair_description
            repair.show_repair_usage_hours = config.show_repair_usage_hours
            repair.show_repair_fleet_vehicle = config.integrate_fleet

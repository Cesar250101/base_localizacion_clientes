# -*- coding: utf-8 -*-

from odoo import api, fields, models


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    fecha_rma = fields.Date(
        string='Fecha RMA',
        default=fields.Date.context_today,
    )
    usage_hours = fields.Float(string='Horas de uso')
    hide_repair_description = fields.Boolean(
        compute='_compute_repair_configuration',
    )
    show_repair_usage_hours = fields.Boolean(
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

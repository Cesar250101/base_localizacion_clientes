# -*- coding: utf-8 -*-

from odoo import api, fields, models


class RepairConfig(models.Model):
    _name = 'repair.config'
    _description = 'Configuración de reparaciones'
    _rec_name = 'company_id'

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='cascade',
    )
    hide_repair_description = fields.Boolean(
        string='Ocultar descripción de la reparación',
    )
    show_repair_usage_hours = fields.Boolean(
        string='Mostrar horas de uso de la unidad o equipo',
    )

    _sql_constraints = [
        (
            'repair_config_company_uniq',
            'unique(company_id)',
            'Solo puede existir una configuración de reparaciones por compañía.',
        ),
    ]

    @api.model
    def get_company_config(self, company=None):
        company = company or self.env.company
        config = self.search([('company_id', '=', company.id)], limit=1)
        if not config:
            config = self.create({'company_id': company.id})
        return config

# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    def _get_default_company_id(self):
        return self.env.company.id

    patente = fields.Char(string='Patente')
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
    usage_hours = fields.Char(string='Horas de uso')
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
    show_patente = fields.Boolean(
        compute='_compute_repair_configuration',
    )
    show_repair_equipo = fields.Boolean(
        compute='_compute_repair_configuration',
    )
    repair_terms_conditions = fields.Html(
        compute='_compute_repair_configuration',
    )
    equipo_id = fields.Many2one(
        'emsin.equipos',
        string='Equipo',
        domain="[('partner_id', '=', partner_id)]",
    )
    stock_picking_count = fields.Integer(
        string='Stock Pickings',
        compute='_compute_stock_picking_count',
    )
    invoice_close_date = fields.Date(
        string='Fecha Cierre',
        compute='_compute_invoice_close_date',
        store=True,
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
            repair.show_patente = config.require_patente
            repair.show_repair_equipo = config.integrate_emsin_equipos
            repair.repair_terms_conditions = config.terms_conditions

    @api.depends('invoice_id', 'invoice_id.invoice_date')
    def _compute_invoice_close_date(self):
        for repair in self:
            if repair.invoice_id:
                repair.invoice_close_date = repair.invoice_id.invoice_date

    def _compute_stock_picking_count(self):
        for repair in self:
            moves = self.env['stock.move'].search([('repair_id', '=', repair.id)])
            repair.stock_picking_count = len(moves.picking_id)

    def action_view_stock_pickings(self):
        moves = self.env['stock.move'].search([('repair_id', '=', self.id)])
        return {
            'name': _('Stock Pickings'),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'stock.picking',
            'domain': [('id', 'in', moves.picking_id.ids)],
        }

    def state_draft(self):
        self.state = 'under_repair'
        return True

    def action_repair_done(self):
        # El override heredado de emsin era una copia incompleta del metodo
        # core (nunca creaba el stock move). No se detecto logica propia
        # distinta a la del core, asi que se delega directamente.
        return super().action_repair_done()

    def action_repair_end(self):
        return super().action_repair_end()

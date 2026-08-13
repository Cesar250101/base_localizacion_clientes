# -*- coding: utf-8 -*-
"""Asistente para sincronizar manualmente un rango de fechas de MatchPoint.

Sirve para recuperar días históricos o reprocesar un rango tras un fallo del
cron. Usa exactamente la misma lógica de importación que la ejecución automática.
"""

from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MatchpointSyncWizard(models.TransientModel):
    _name = 'matchpoint.sync.wizard'
    _description = 'Sincronizar pagos de MatchPoint'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company)
    date_from = fields.Date(
        string='Desde', required=True,
        default=lambda self: fields.Date.context_today(self) - timedelta(days=1))
    date_to = fields.Date(
        string='Hasta', required=True,
        default=lambda self: fields.Date.context_today(self))

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from > wizard.date_to:
                raise UserError(_('La fecha "Desde" no puede ser posterior a "Hasta".'))
            if (wizard.date_to - wizard.date_from).days > 7:
                raise UserError(_(
                    'El endpoint /sales de MatchPoint admite un rango máximo de 7 días. '
                    'Divida la consulta en tramos más cortos.'))

    def action_sync(self):
        self.ensure_one()
        if not self.company_id.matchpoint_enabled:
            raise UserError(_(
                'La compañía %s no tiene habilitada la integración con MatchPoint.',
                self.company_id.name))

        resumen = self.company_id._matchpoint_sync_range(self.date_from, self.date_to)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronización finalizada'),
                'message': _(
                    '%(creadas)s boleta(s) creada(s), %(omitidas)s omitida(s), '
                    '%(errores)s con error.',
                    creadas=resumen['creadas'],
                    omitidas=resumen['omitidas'],
                    errores=resumen['errores']),
                'type': 'warning' if resumen['errores'] else 'success',
                'sticky': bool(resumen['errores']),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

# -*- coding: utf-8 -*-

from odoo import models, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_open_import_lines_wizard(self):
        """Abrir el wizard para importar líneas desde Excel"""
        self.ensure_one()
        
        # Crear el registro del wizard con el purchase_order_id
        wizard = self.env['import.purchase.lines.wizard'].create({
            'purchase_order_id': self.id,
        })
        
        return {
            'name': 'Importar Líneas de Orden de Compra',
            'type': 'ir.actions.act_window',
            'res_model': 'import.purchase.lines.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

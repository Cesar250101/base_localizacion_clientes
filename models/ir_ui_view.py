# -*- coding: utf-8 -*-
from odoo import models


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    def _register_hook(self):
        super()._register_hook()
        self._sync_report_saleorder_legacy_producto_column()

    def _sync_report_saleorder_legacy_producto_column(self):
        """Activa report_saleorder_document_inherit_localizacion_legacy_producto
        únicamente en las bases donde la vista base sale.report_saleorder_document
        fue reescrita a mano y ya trae una columna th_producto/td_product_id
        (caso detectado en clicksale). En las demás bases esos nombres no existen
        en el arch base y el template debe quedar inactivo, o su xpath fallaría.
        """
        base_view = self.env.ref('sale.report_saleorder_document', raise_if_not_found=False)
        legacy_view = self.env.ref(
            'base_localizacion_clientes.report_saleorder_document_inherit_localizacion_legacy_producto',
            raise_if_not_found=False,
        )
        if not base_view or not legacy_view:
            return
        arch = base_view.arch_db or ''
        has_legacy_column = 'name="th_producto"' in arch and 'name="td_product_id"' in arch
        if legacy_view.active != has_legacy_column:
            legacy_view.sudo().active = has_legacy_column

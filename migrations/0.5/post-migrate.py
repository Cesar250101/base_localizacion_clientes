# -*- coding: utf-8 -*-

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Sincroniza la columna estándar Cliente con el nombre ya preservado."""
    cr.execute("""
        UPDATE account_move
           SET invoice_partner_display_name = original_partner_name
         WHERE move_type IN (
             'out_invoice', 'out_refund', 'out_receipt',
             'in_invoice', 'in_refund', 'in_receipt'
         )
           AND COALESCE(original_partner_name, '') != ''
           AND invoice_partner_display_name IS DISTINCT FROM original_partner_name
    """)
    _logger.info(
        'Se sincronizó el nombre mostrado de %s documentos comerciales.',
        cr.rowcount,
    )

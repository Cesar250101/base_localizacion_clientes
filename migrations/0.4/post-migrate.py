# -*- coding: utf-8 -*-

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Completa el nombre original de los documentos comerciales existentes."""
    cr.execute("""
        UPDATE account_move AS move
           SET original_partner_name = partner.name,
               invoice_partner_display_name = partner.name
          FROM res_partner AS partner
         WHERE move.partner_id = partner.id
           AND move.move_type IN (
               'out_invoice', 'out_refund', 'out_receipt',
               'in_invoice', 'in_refund', 'in_receipt'
           )
           AND COALESCE(move.original_partner_name, '') = ''
    """)
    _logger.info(
        'Se completó el nombre original en %s documentos comerciales existentes.',
        cr.rowcount,
    )

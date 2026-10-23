# -*- coding: utf-8 -*-

from odoo.addons.base_localizacion_clientes.hooks import populate_partner_companies


def migrate(cr, version):
    """BASELOCCLI-009: copia la compañía principal de cada contacto a la lista.

    partner_company_ids (tabla res_partner_company_rel) nace vacía; se deja en
    ella la compañía de res_partner.company_id para cumplir el invariante
    «la principal está en la lista». Es idempotente: no duplica filas. La lógica
    está en hooks.populate_partner_companies, compartida con el post_init_hook.
    """
    populate_partner_companies(cr)

# -*- coding: utf-8 -*-

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# Dominio original de base.res_partner_rule (core, noupdate="1"). Este módulo lo
# redefine con partner_company_ids (BASELOCCLI-009); al desinstalar hay que
# devolverlo o cualquier búsqueda de contactos de un usuario no superusuario falla
# con «Invalid field res.partner.partner_company_ids in leaf».
CORE_PARTNER_RULE_DOMAIN = (
    "['|', ('partner_share', '=', False), ('company_id', 'in', company_ids + [False])]")

# Acciones del core que este módulo filtra por partner_company_ids y su contexto original.
_CORE_ACTIONS_CONTEXT = {
    'contacts.action_contacts': "{'default_is_company': True}",
    'account.res_partner_action_customer': None,
}


def populate_partner_companies(cr):
    """Copia res_partner.company_id a res_partner_company_rel (idempotente).

    Deja la compañía principal de cada contacto en partner_company_ids. Lo usan la
    migración 0.8 (-u) y el post_init_hook (-i): las migraciones solo corren en -u,
    así que en una instalación nueva sobre una base con contactos la lista quedaría
    vacía y los contactos saldrían de los dominios por partner_company_ids.
    Devuelve las filas agregadas.
    """
    cr.execute("SELECT to_regclass('res_partner_company_rel')")
    if not cr.fetchone()[0]:
        _logger.warning(
            'No existe res_partner_company_rel: no se copiaron las compañías de los contactos.')
        return 0
    cr.execute("""
        INSERT INTO res_partner_company_rel (partner_id, company_id)
        SELECT p.id, p.company_id
          FROM res_partner p
         WHERE p.company_id IS NOT NULL
           AND NOT EXISTS (
               SELECT 1
                 FROM res_partner_company_rel r
                WHERE r.partner_id = p.id
                  AND r.company_id = p.company_id
           )
    """)
    _logger.info(
        'Se agregó la compañía principal a la lista de compañías de %s contactos.',
        cr.rowcount,
    )
    return cr.rowcount


def post_init_hook(cr, registry):
    populate_partner_companies(cr)


def uninstall_hook(cr, registry):
    """Devuelve al core lo que este módulo redefinió con partner_company_ids.

    Idempotente: no escribe lo que ya está como en el core.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    rule = env.ref('base.res_partner_rule', raise_if_not_found=False)
    if rule and rule.domain_force != CORE_PARTNER_RULE_DOMAIN:
        rule.domain_force = CORE_PARTNER_RULE_DOMAIN
    # Estas acciones son del core (no se borran al desinstalar) y quedarían con un
    # dominio sobre un campo que ya no existe.
    for xmlid, core_context in _CORE_ACTIONS_CONTEXT.items():
        action = env.ref(xmlid, raise_if_not_found=False)
        if not action:
            continue
        if action.domain and 'partner_company_ids' in action.domain:
            action.domain = False
        if core_context and 'company_contacts' in (action.context or ''):
            action.context = core_context

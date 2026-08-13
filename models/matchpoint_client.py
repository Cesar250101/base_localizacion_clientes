# -*- coding: utf-8 -*-
"""Cliente HTTP para la Query API de MatchPoint.

La API es de solo lectura: expone únicamente endpoints GET bajo /api/query,
autenticados con la cabecera X-Api-Token. No dispone de webhooks, por lo que la
integración consulta periódicamente (ver res_company._cron_matchpoint_sync).

Límites documentados que este cliente respeta:
  - Envoltorio de respuesta {ok, data, offset, limit, hasMore}.
  - Paginación incrementando offset en limit mientras hasMore sea verdadero.
  - Cuota diaria por token (500 peticiones/día por defecto) -> HTTP 429.
"""

import logging

import requests

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Tope defensivo de páginas por consulta: evita agotar la cuota diaria del token
# si la API devolviera hasMore=True de forma indefinida.
MAX_PAGINAS = 50


class MatchpointClient(models.AbstractModel):
    _name = 'matchpoint.client'
    _description = 'Cliente de la Query API de MatchPoint'

    def _matchpoint_get(self, company, endpoint, params=None):
        """Ejecuta un GET contra /api/query/<endpoint> y devuelve el cuerpo JSON.

        Traduce los códigos de error documentados por la API a mensajes en
        español, para no exponer trazas crudas al usuario final.
        """
        company = company.sudo()
        base_url = (company.matchpoint_base_url or '').rstrip('/')
        url = '%s/api/query/%s' % (base_url, endpoint)
        try:
            response = requests.get(
                url,
                headers={'X-Api-Token': company.matchpoint_api_token},
                params=params or {},
                timeout=company.matchpoint_timeout or 30,
            )
        except requests.RequestException as error:
            _logger.exception('MatchPoint: fallo de red consultando %s', url)
            raise UserError(_(
                'No se pudo conectar con MatchPoint (%s). Verifique la URL base '
                'y la conectividad del servidor.', error)) from error

        if response.status_code == 400:
            raise UserError(_(
                'MatchPoint rechazó la consulta (400): %s',
                self._matchpoint_error_message(response)))
        if response.status_code == 401:
            raise UserError(_(
                'Token de MatchPoint inválido, inactivo o sin el permiso "query" (401).'))
        if response.status_code == 429:
            raise UserError(_(
                'Se agotó la cuota diaria de peticiones del token de MatchPoint (429). '
                'El contador se reinicia a medianoche.'))
        if response.status_code >= 400:
            raise UserError(_(
                'MatchPoint devolvió un error HTTP %(codigo)s: %(mensaje)s',
                codigo=response.status_code,
                mensaje=self._matchpoint_error_message(response)))

        try:
            payload = response.json()
        except ValueError as error:
            _logger.error('MatchPoint: respuesta no JSON desde %s', url)
            raise UserError(_(
                'MatchPoint devolvió una respuesta que no es JSON válido.')) from error

        if not payload.get('ok'):
            raise UserError(_(
                'MatchPoint respondió con error: %s',
                payload.get('error') or _('sin detalle')))
        return payload

    def _matchpoint_error_message(self, response):
        """Extrae el campo `error` del envoltorio, con respaldo al texto crudo."""
        try:
            return response.json().get('error') or response.text[:200]
        except ValueError:
            return response.text[:200]

    def _matchpoint_get_all(self, company, endpoint, params=None, page_size=None):
        """Devuelve todos los registros de un endpoint, paginando por offset."""
        registros = []
        params = dict(params or {})
        offset = 0
        for _pagina in range(MAX_PAGINAS):
            consulta = dict(params, offset=offset)
            if page_size:
                consulta['limit'] = page_size
            payload = self._matchpoint_get(company, endpoint, consulta)
            datos = payload.get('data') or []
            registros.extend(datos)
            if not payload.get('hasMore') or not datos:
                break
            # La API devuelve el limit realmente aplicado (lo recorta del lado
            # servidor), así que se avanza con ese valor y no con el solicitado.
            offset += payload.get('limit') or len(datos)
        else:
            _logger.warning(
                'MatchPoint: se alcanzó el tope de %s páginas consultando %s; '
                'puede haber registros sin importar.', MAX_PAGINAS, endpoint)
        return registros

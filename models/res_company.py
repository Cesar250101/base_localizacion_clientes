# -*- coding: utf-8 -*-

import logging
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# El endpoint /sales usa límites propios: por defecto y tope 3000 registros.
MATCHPOINT_SALES_PAGE_SIZE = 3000


class TopePlanesERP(models.Model):
    _name = 'base_localiazcion_clientes.planes_topes'
    _description = 'Topes para cada plan de ERP'

    name = fields.Char(string='Nombre Plan')    
    max_dtes = fields.Integer(string='Maximo DTEs',default=30)
    max_ventas=fields.Integer(string='Maximo Ventas', default=6000000)



class ResCompany(models.Model):
    _inherit = 'res.company'

    planes_topes_id = fields.Many2one(comodel_name='base_localiazcion_clientes.planes_topes', string='Tipo de Plan')
    store_original_partner_name = fields.Boolean(
        string='Conservar nombre original del contacto',
        help='Guarda en los documentos comerciales el nombre del contacto al '
             'momento de publicarlos.',
    )
    integrar_gestioo = fields.Boolean(string='Integrar con Gestioo')
    token_gestioo = fields.Char(string='Token de Gestioo')
    url_webhook_gestioo = fields.Char(string='URL Webhook Gestioo', 
                                      compute='_compute_url_webhook_gestioo',
                                      help='URL que debe configurarse en Gestioo para enviar los datos a Odoo.')

    es_taller = fields.Boolean(string='Es Taller')

    # --- Integración MatchPoint (Query API) ---------------------------------
    # La API de MatchPoint es de solo lectura (solo endpoints GET, sin webhooks),
    # por lo que la sincronización se hace con el cron _cron_matchpoint_sync.
    matchpoint_enabled = fields.Boolean(string='Integrar con MatchPoint')
    matchpoint_base_url = fields.Char(
        string='URL Base API',
        help='Host de la API, sin la ruta /api/query. Ej: https://cliente.matchpoint.com.es')
    matchpoint_api_token = fields.Char(
        string='Token API', groups='base.group_system',
        help='Se envía en la cabecera X-Api-Token. El token debe tener el permiso "query".')
    matchpoint_center_code = fields.Char(
        string='Código de Centro',
        help='Filtro "center" de la API (campo centerCode). Vacío = todos los centros.')
    matchpoint_timeout = fields.Integer(
        string='Tiempo máximo de espera (segundos)', default=30)

    matchpoint_document_class_id = fields.Many2one(
        'sii.document_class', string='Tipo de documento',
        domain=[('sii_code', 'in', [39, 41])],
        help='Documento tributario a emitir por cada pago de MatchPoint. '
             'La Boleta Exenta (41) es el valor habitual. El tipo debe coincidir '
             'con el CAF cargado y con la secuencia configurada en el punto de venta.')

    matchpoint_pos_config_id = fields.Many2one(
        'pos.config', string='Punto de venta destino',
        help='Punto de venta donde se registrarán las órdenes importadas. '
             'Debe tener configurada la secuencia del documento seleccionado.')
    matchpoint_product_id = fields.Many2one(
        'product.product', string='Producto por defecto',
        help='Se usa cuando la referencia de la línea de MatchPoint no existe en Odoo.')
    matchpoint_payment_method_id = fields.Many2one(
        'pos.payment.method', string='Método de pago',
        help='Método de pago del POS con el que se registrarán los cobros de MatchPoint.')

    matchpoint_last_sync = fields.Datetime(
        string='Última sincronización', readonly=True, copy=False)
    matchpoint_lookback_days = fields.Integer(
        string='Días hacia atrás', default=2,
        help='Ventana de días que se vuelve a consultar en cada ejecución para '
             'recuperar pagos registrados con retraso. Máximo 7 por límite de la API.')

    @api.constrains('matchpoint_lookback_days')
    def _check_matchpoint_lookback_days(self):
        for company in self:
            if not company.matchpoint_enabled:
                continue
            if not 1 <= company.matchpoint_lookback_days <= 7:
                raise ValidationError(_(
                    'Los "Días hacia atrás" de MatchPoint deben estar entre 1 y 7: '
                    'el endpoint /sales rechaza rangos mayores a 7 días.'))

    def _matchpoint_validate_configuration(self):
        """Verifica que la compañía tenga todo lo necesario para sincronizar.

        Acumula todos los campos faltantes y levanta un único ValidationError,
        para que el usuario los corrija de una sola vez.
        """
        self.ensure_one()
        company = self.sudo()
        requeridos = [
            (company.matchpoint_base_url, _('URL Base API')),
            (company.matchpoint_api_token, _('Token API')),
            (company.matchpoint_document_class_id, _('Tipo de documento')),
            (company.matchpoint_pos_config_id, _('Punto de venta destino')),
            (company.matchpoint_product_id, _('Producto por defecto')),
            (company.matchpoint_payment_method_id, _('Método de pago')),
        ]
        faltantes = [etiqueta for valor, etiqueta in requeridos if not valor]
        if faltantes:
            raise ValidationError(_(
                'Falta configurar la integración con MatchPoint en la compañía %(compania)s: %(campos)s',
                compania=self.name, campos=', '.join(faltantes)))

        # El POS rechaza pagos con un método que no esté habilitado en su
        # configuración (pos.payment._check_payment_method_id).
        config = company.matchpoint_pos_config_id
        if company.matchpoint_payment_method_id not in config.payment_method_ids:
            raise ValidationError(_(
                'El método de pago "%(metodo)s" no está habilitado en el punto de '
                'venta "%(pos)s". Agréguelo en la configuración del punto de venta '
                'o elija otro método.',
                metodo=company.matchpoint_payment_method_id.display_name,
                pos=config.display_name))

    def action_matchpoint_test_connection(self):
        """Consulta un registro a /customers para validar URL y token."""
        self.ensure_one()
        self._matchpoint_validate_configuration()
        datos = self.env['matchpoint.client']._matchpoint_get(
            self, 'customers', {'limit': 1})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Conexión exitosa'),
                'message': _('MatchPoint respondió correctamente (%s registro(s) recibido(s)).',
                             len(datos.get('data') or [])),
                'type': 'success',
                'sticky': False,
            },
        }

    def _matchpoint_sync_range(self, date_from, date_to):
        """Importa los documentos de /sales del rango dado en esta compañía."""
        self.ensure_one()
        self._matchpoint_validate_configuration()

        if (date_to - date_from).days > 7:
            raise UserError(_(
                'El endpoint /sales de MatchPoint admite un rango máximo de 7 días.'))

        params = {
            'dateFrom': date_from.strftime('%Y-%m-%d'),
            'dateTo': date_to.strftime('%Y-%m-%d'),
        }
        if self.sudo().matchpoint_center_code:
            params['center'] = self.sudo().matchpoint_center_code

        ventas = self.env['matchpoint.client']._matchpoint_get_all(
            self, 'sales', params, page_size=MATCHPOINT_SALES_PAGE_SIZE)
        resumen = self.env['pos.order']._matchpoint_import_sales(self, ventas)
        self.sudo().matchpoint_last_sync = fields.Datetime.now()
        _logger.info(
            'MatchPoint [%s] %s a %s: %s documentos recibidos, %s creados, '
            '%s omitidos, %s con error.',
            self.name, params['dateFrom'], params['dateTo'], len(ventas),
            resumen['creadas'], resumen['omitidas'], resumen['errores'])
        return resumen

    @api.model
    def _cron_matchpoint_sync(self):
        """Cron: sincroniza las compañías con MatchPoint habilitado.

        Se reconsulta una ventana de varios días para recuperar pagos
        registrados con retraso; la restricción única de pos.order sobre
        matchpoint_sale_id evita que ese solape genere boletas duplicadas.
        """
        companies = self.search([('matchpoint_enabled', '=', True)])
        for company in companies:
            dias = min(max(company.matchpoint_lookback_days or 2, 1), 7)
            date_to = fields.Date.context_today(company)
            date_from = date_to - timedelta(days=dias)
            try:
                company._matchpoint_sync_range(date_from, date_to)
            except Exception:
                # Una compañía mal configurada o una API caída no debe impedir
                # que el resto se sincronice.
                _logger.exception(
                    'MatchPoint: fallo sincronizando la compañía %s', company.name)
        return True

    @api.depends('integrar_gestioo','token_gestioo')
    def _compute_url_webhook_gestioo(self):
        for record in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            record.url_webhook_gestioo = f"{base_url}/base_localizacion_clientes/gestioo?token={record.token_gestioo}" if record.token_gestioo else ""
    
    @api.model
    def _default_project_time_mode_id(self):
        uom = self.env.ref('uom.product_uom_hour', raise_if_not_found=False)
        wtime = self.env.ref('uom.uom_categ_wtime')
        if not uom:
            uom = self.env['uom.uom'].search([('category_id', '=', wtime.id), ('uom_type', '=', 'reference')], limit=1)
        if not uom:
            uom = self.env['uom.uom'].search([('category_id', '=', wtime.id)], limit=1)
        return uom

    @api.model
    def _default_timesheet_encode_uom_id(self):
        uom = self.env.ref('uom.product_uom_hour', raise_if_not_found=False)
        wtime = self.env.ref('uom.uom_categ_wtime')
        if not uom:
            uom = self.env['uom.uom'].search([('category_id', '=', wtime.id), ('uom_type', '=', 'reference')], limit=1)
        if not uom:
            uom = self.env['uom.uom'].search([('category_id', '=', wtime.id)], limit=1)
        return uom
    timesheet_encode_uom_id = fields.Many2one('uom.uom', string="Timesheet Encoding Unit",
        default=_default_timesheet_encode_uom_id, domain=lambda self: [('category_id', '=', self.env.ref('uom.uom_categ_wtime').id)])
    
    project_time_mode_id = fields.Many2one('uom.uom', string='Project Time Unit',
        default=_default_project_time_mode_id,
        help="This will set the unit of measure used in projects and tasks.\n"
             "If you use the timesheet linked to projects, don't "
             "forget to setup the right unit of measure in your employees.")
    internal_project_id = fields.Many2one(
        'project.project', string="Internal Project",
        help="Default project value for timesheet generated from time off type.")
    

    @api.model_create_multi
    def create(self, vals_list):
        # Marca el contexto para que res.partner NO fuerce company_id en la
        # dirección autocreada de la compañía nueva (ver res_partner.py). Sin esto,
        # el partner nace con la company activa y falla el check de multi-compañía.
        # No dependemos de que partner_company_default esté instalado.
        self = self.with_context(creating_from_company=True)
        # Crear la compañía usando el método original
        companies = super(ResCompany, self).create(vals_list)
        # Agregar las compañías creadas a las empresas permitidas del usuario actual
        
        user = self.env.user
        user.write({
                    'company_ids': [(4, companies.id)]
                })
        

        # Desactivar la regla de compañía para las listas de precios
        pricelist_company_rule = self.env.ref('product.product_pricelist_comp_rule', raise_if_not_found=False)
        if pricelist_company_rule:
            pricelist_company_rule.active = False
        # Por cada compañía creada, crear su lista de precios
        for company in companies:
            self.env['product.pricelist'].sudo().create({
                'name': f'Lista de Precios - {company.name}',
                'currency_id': company.currency_id.id,
                'company_id': company.id,
                'sequence': 1,
                'active': True,
            })
        # Reactivar la regla de compañía para las listas de precios
        pricelist_company_rule.active = True
        return companies

    @api.model
    def _sync_contacts_action_domain(self):
        action = self.env.ref('contacts.action_contacts', raise_if_not_found=False)
        if not action:
            return
        companies = self.env['res.company'].search([])
        if len(companies) == 1:
            action.domain = "['|', ('company_id', '=', %d), ('company_id', '=', False)]" % companies.id

# -*- coding: utf-8 -*-
"""Creación de órdenes POS a partir de los documentos de venta de MatchPoint.

Una vez creada la orden con su document_class_id, la emisión del DTE (folio,
timbre y envío al SII) la realiza l10n_cl_dte_point_of_sale en su override de
action_pos_order_paid; aquí no se habla con el SII.
"""

import logging
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    matchpoint_sale_id = fields.Char(
        string='ID Venta MatchPoint', index=True, copy=False, readonly=True)
    matchpoint_doc_number = fields.Char(
        string='N° Documento MatchPoint', copy=False, readonly=True)
    matchpoint_sync_date = fields.Datetime(
        string='Fecha de sincronización', copy=False, readonly=True)

    _sql_constraints = [
        ('matchpoint_sale_uniq',
         'unique(matchpoint_sale_id, company_id)',
         'Ya existe una orden POS para este documento de MatchPoint.'),
    ]

    # -- Utilidades ---------------------------------------------------------

    @api.model
    def _matchpoint_parse_datetime(self, valor):
        """Convierte 'yyyy-MM-dd HH:mm' o 'yyyy-MM-dd' a datetime naive (UTC)."""
        if not valor:
            return False
        for formato in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
            try:
                return datetime.strptime(valor, formato)
            except ValueError:
                continue
        _logger.warning('MatchPoint: fecha con formato desconocido: %s', valor)
        return False

    @api.model
    def _matchpoint_get_session(self, company):
        """Devuelve una sesión abierta del POS destino, abriéndola si hace falta.

        El cron debe poder operar sin intervención humana, por eso abre la sesión
        cuando no existe ninguna en curso.
        """
        config = company.sudo().matchpoint_pos_config_id
        session = self.env['pos.session'].sudo().search([
            ('config_id', '=', config.id),
            ('state', '=', 'opened'),
        ], limit=1, order='id desc')
        if session:
            return session

        session = self.env['pos.session'].sudo().create({
            'config_id': config.id,
            'user_id': self.env.user.id,
        })
        # opening_control -> opened; sin esto la orden no puede registrarse.
        if session.state == 'opening_control':
            session.action_pos_session_open()
        _logger.info(
            'MatchPoint: sesión POS %s abierta automáticamente en %s',
            session.name, config.name)
        return session

    @api.model
    def _matchpoint_find_partner(self, company, sale):
        """Busca el cliente por RUT y luego por nombre; lo crea si no existe.

        En boleta el receptor es opcional, así que se devuelve un recordset
        vacío cuando MatchPoint no aporta datos identificatorios.
        """
        Partner = self.env['res.partner'].sudo()
        vat = (sale.get('customerIdent') or '').strip()
        nombre = (sale.get('customerName') or '').strip()

        if vat:
            partner = Partner.search([
                ('vat', '=', vat),
                ('company_id', 'in', [False, company.id]),
            ], limit=1)
            if partner:
                return partner
        if not vat and not nombre:
            return Partner.browse()
        if nombre:
            partner = Partner.search([
                ('name', '=ilike', nombre),
                ('company_id', 'in', [False, company.id]),
            ], limit=1)
            if partner:
                return partner
        if not nombre:
            return Partner.browse()

        return Partner.create({
            'name': nombre,
            'vat': vat or False,
            'company_id': company.id,
        })

    @api.model
    def _matchpoint_line_taxes(self, company, product):
        """Impuestos a aplicar en la línea según el documento configurado.

        En boleta exenta (38/41) NO se deja la línea sin impuestos: el timbrado
        de l10n_cl_dte_point_of_sale (_invoice_lines) rechaza las líneas sin
        impuesto, y necesita uno de tasa 0 para marcar IndExe en el XML. Por eso
        se busca el impuesto exento de venta de la compañía.
        En boleta afecta se respetan los impuestos del producto.
        """
        document_class = company.sudo().matchpoint_document_class_id
        if document_class.es_boleta_exenta():
            return [(6, 0, self._matchpoint_exempt_tax(company).ids)]
        impuestos = product.taxes_id.filtered(
            lambda t: t.company_id == company)
        if not impuestos:
            # Sin impuestos el DTE no se puede timbrar; se cae al exento.
            impuestos = self._matchpoint_exempt_tax(company)
        return [(6, 0, impuestos.ids)]

    @api.model
    def _matchpoint_exempt_tax(self, company):
        """Impuesto de venta exento (tasa 0) de la compañía.

        Es el que hace que el DTE se emita con IndExe=1 en cada línea.
        """
        impuesto = self.env['account.tax'].sudo().search([
            ('company_id', '=', company.id),
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', 0.0),
        ], limit=1, order='sii_code, id')
        if not impuesto:
            raise UserError(_(
                'No existe un impuesto de venta exento (tasa 0%%) en la compañía '
                '%s. Cree uno para poder emitir boletas exentas.', company.name))
        return impuesto

    @api.model
    def _matchpoint_prepare_lines(self, company, sale):
        """Construye los comandos de pos.order.line desde sale['lines'].

        Los precios de MatchPoint vienen netos (`price`) junto con su IVA. Para
        boleta exenta se usa el total de la línea, de modo que la suma de la
        orden coincida exactamente con `total` del documento.
        """
        Product = self.env['product.product'].sudo()
        document_class = company.sudo().matchpoint_document_class_id
        es_exenta = document_class.es_boleta_exenta()
        comandos = []

        for linea in sale.get('lines') or []:
            referencia = (linea.get('reference') or '').strip()
            producto = Product.browse()
            if referencia:
                producto = Product.search([
                    ('default_code', '=', referencia),
                    ('company_id', 'in', [False, company.id]),
                ], limit=1)
            if not producto:
                producto = company.matchpoint_product_id
                if referencia:
                    _logger.info(
                        'MatchPoint: referencia "%s" no encontrada, se usa el '
                        'producto por defecto %s', referencia, producto.display_name)

            cantidad = float(linea.get('quantity') or 0.0)
            if not cantidad:
                continue
            # En exenta el precio unitario incluye todo (no hay impuesto que
            # desglosar); en afecta se mantiene el neto y el impuesto lo calcula
            # Odoo a partir de tax_ids.
            importe = float(linea.get('total') if es_exenta else linea.get('amount') or 0.0)
            precio_unitario = importe / cantidad

            impuestos = self._matchpoint_line_taxes(company, producto)
            comandos.append((0, 0, dict(
                self._matchpoint_line_subtotals(
                    company, producto, precio_unitario, cantidad, impuestos),
                name=(linea.get('description') or producto.display_name or '/')[:250],
                product_id=producto.id,
                qty=cantidad,
                price_unit=precio_unitario,
                discount=0.0,
                tax_ids=impuestos,
            )))

        if not comandos:
            # Documento sin detalle: se sintetiza una línea única por el total,
            # para no perder el ingreso ni la boleta.
            total = float(sale.get('total') or 0.0)
            producto = company.sudo().matchpoint_product_id
            impuestos = self._matchpoint_line_taxes(company, producto)
            comandos.append((0, 0, dict(
                self._matchpoint_line_subtotals(
                    company, producto, total, 1.0, impuestos),
                name=(sale.get('description') or producto.display_name or '/')[:250],
                product_id=producto.id,
                qty=1.0,
                price_unit=total,
                discount=0.0,
                tax_ids=impuestos,
            )))
        return comandos

    @api.model
    def _matchpoint_line_subtotals(self, company, product, price_unit, qty, tax_commands):
        """Calcula price_subtotal / price_subtotal_incl de la línea.

        Ambos son obligatorios a nivel de base de datos y en el flujo normal del
        POS los envía el frontend, así que al crear la orden desde el servidor
        hay que calcularlos aquí replicando _compute_amount_line_all.
        """
        impuesto_ids = tax_commands[0][2] if tax_commands else []
        impuestos = self.env['account.tax'].browse(impuesto_ids)
        moneda = company.currency_id
        totales = impuestos.compute_all(
            price_unit, moneda, qty, product=product)
        return {
            'price_subtotal': totales['total_excluded'],
            'price_subtotal_incl': totales['total_included'],
        }

    # -- Creación de la orden -----------------------------------------------

    @api.model
    def _matchpoint_should_skip(self, company, sale):
        """Motivo por el que un documento no debe convertirse en boleta, o None."""
        if sale.get('isCanceled'):
            return _('documento anulado')
        if not sale.get('paid'):
            return _('documento no pagado')
        if float(sale.get('total') or 0.0) <= 0:
            return _('total menor o igual a cero')
        if not sale.get('id'):
            return _('documento sin identificador')
        existente = self.sudo().search([
            ('matchpoint_sale_id', '=', str(sale['id'])),
            ('company_id', '=', company.id),
        ], limit=1)
        if existente:
            return _('ya importado como %s', existente.name)
        return None

    @api.model
    def _matchpoint_create_order_from_sale(self, company, sale):
        """Crea una pos.order pagada a partir de un documento de MatchPoint.

        Devuelve la orden creada, o un recordset vacío si el documento se omitió.
        """
        motivo = self._matchpoint_should_skip(company, sale)
        if motivo:
            _logger.debug(
                'MatchPoint: documento %s omitido (%s)', sale.get('id'), motivo)
            return self.browse()

        company = company.sudo()
        session = self._matchpoint_get_session(company)
        partner = self._matchpoint_find_partner(company, sale)
        lineas = self._matchpoint_prepare_lines(company, sale)
        fecha = (self._matchpoint_parse_datetime(sale.get('payDate'))
                 or self._matchpoint_parse_datetime(sale.get('date'))
                 or fields.Datetime.now())

        # Los importes de la cabecera no son calculados: en el flujo normal del
        # POS los envía el frontend, así que se totalizan aquí desde las líneas.
        base = sum(v['price_subtotal'] for _c, _i, v in lineas)
        total = sum(v['price_subtotal_incl'] for _c, _i, v in lineas)

        orden = self.sudo().create({
            'company_id': company.id,
            'session_id': session.id,
            'partner_id': partner.id or False,
            'date_order': fecha,
            'pricelist_id': session.config_id.pricelist_id.id or False,
            'lines': lineas,
            'document_class_id': company.matchpoint_document_class_id.id,
            'matchpoint_sale_id': str(sale['id']),
            'matchpoint_doc_number': sale.get('docNumber') or False,
            'matchpoint_sync_date': fields.Datetime.now(),
            'amount_tax': total - base,
            'amount_total': total,
            'amount_paid': 0.0,
            'amount_return': 0.0,
        })

        # El importe del pago debe cuadrar exactamente con amount_total: en caso
        # contrario action_pos_order_paid levanta "Order is not fully paid".
        self.env['pos.payment'].sudo().create({
            'pos_order_id': orden.id,
            'payment_method_id': company.matchpoint_payment_method_id.id,
            'amount': total,
            'payment_date': fecha,
        })
        orden.sudo().amount_paid = sum(orden.payment_ids.mapped('amount'))

        # Dispara el override de l10n_cl_dte_point_of_sale: asigna folio, timbra
        # el DTE y lo encola para envío al SII.
        orden.action_pos_order_paid()
        _logger.info(
            'MatchPoint: documento %s importado como orden POS %s (folio %s)',
            sale['id'], orden.name, orden.sii_document_number)
        return orden

    @api.model
    def _matchpoint_import_sales(self, company, ventas):
        """Procesa un lote de documentos aislando los fallos individuales.

        Cada documento va en su propio savepoint: un error en uno no descarta
        los ya importados ni aborta el resto del lote.
        """
        resumen = {'creadas': 0, 'omitidas': 0, 'errores': 0}
        for venta in ventas:
            try:
                with self.env.cr.savepoint():
                    orden = self._matchpoint_create_order_from_sale(company, venta)
                resumen['creadas' if orden else 'omitidas'] += 1
            except Exception:
                resumen['errores'] += 1
                _logger.exception(
                    'MatchPoint: error importando el documento %s de la compañía %s',
                    venta.get('id'), company.name)
        return resumen

    def action_matchpoint_open_sale(self):
        """Acción informativa: muestra el identificador de origen."""
        self.ensure_one()
        raise UserError(_(
            'Orden importada desde MatchPoint.\nID de venta: %(id)s\nDocumento: %(doc)s',
            id=self.matchpoint_sale_id or '-',
            doc=self.matchpoint_doc_number or '-'))

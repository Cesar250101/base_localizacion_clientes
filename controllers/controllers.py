# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json



class BaseLocalizacionClientes(http.Controller):

    @http.route('/base_localizacion_clientes/gestioo', auth='public', csrf=False)
    def process_order(self, token=None, **kw):
        # Autenticación básica por token desde URL
        if not token:
            return {'error': 'Token requerido'}

        #Obtener la compañía asociada al token
        company = request.env['res.company'].sudo().search([('token_gestioo', '=', token)], limit=1)
        if company.integrar_gestioo == False:
            return {'error': 'La integración con Gestioo no está habilitada para esta compañía'}
        #Ontener el json desde el cuerpo de la solicitud
        try:
            data = json.loads(request.httprequest.data)
        except json.JSONDecodeError:
            return {'error': 'JSON inválido'}

        if data['orden']:
            if data['orden']['area_nombre'] == 'Salida':
                vat=data['orden']['cliente_dni']
                vat = 'CL' + vat.replace('-','').replace('-','')
                partner_id =  request.env['res.partner'].sudo().search([('gestioo_id', '=', data['orden']['cliente_id']),
                                                                        ('company_id', '=', company.id)], limit=1)
                if not partner_id and vat:
                    partner_id =  request.env['res.partner'].sudo().search([('vat', '=', vat),
                                                                            ('company_id', '=', company.id)], limit=1)
                    if partner_id:
                        partner_id.sudo().write({
                            'gestioo_id': data['orden']['cliente_id'],
                            'name': data['orden']['cliente_nombre'] +' '+data['orden']['cliente_apellido'],
                        })
                if not partner_id:
                    partner_id = request.env['res.partner'].sudo().create({
                        'name': data['orden']['cliente_nombre'],
                        'vat': vat,
                        'document_number':data['orden']['cliente_dni'],
                        'street': data['orden']['cliente_direccion'],
                        'phone': data['orden']['cliente_telefono'],
                        'email': data['orden']['cliente_correo'],
                        'company_id': company.id,
                        'gestioo_id': data['orden']['cliente_id'],
                        'company_id': company.id,
                    })                  
                #Buscar por gestioo_id la orden de venta
                order_id = request.env['sale.order'].sudo().search([('gestioo_id', '=', data['orden']['id'])], limit=1)
                if order_id:
                    return {'status': 'Orden ya existe'}
                #Obtengo el usuario para agregarlos como vendedor a la nota de venta
                user_id = request.env['res.users'].sudo().search([('gestioo_id', '=', data['orden']['responsable_id'])], limit=1)
                nombre=data['orden']['responsable_nombre']+' '+ data['orden']['responsable_apellido']
                if not user_id:
                    user_id = request.env['res.users'].sudo().search([('name', '=', nombre)], limit=1)                
                    if user_id:
                        user_id.sudo().write({
                            'gestioo_id': data['orden']['responsable_id'],
                        })
                if not user_id:
                    values={
                        'name': nombre,
                        'login': nombre,
                        'gestioo_id': data['orden']['responsable_id'],
                        'company_id': company.id,
                        'company_ids': [(6, 0, [company.id])],
                        'email': nombre,
                        'groups_id': [(6, 0, [request.env.ref('base.group_user').id])],
                    }
                    print(values)
                    user_id = request.env['res.users'].sudo().create(values)
                # Creo la orden de venta
                order_id = request.env['sale.order'].sudo().create({
                    'name': data['orden']['orden_numeracion'],
                    'partner_id': partner_id.id,
                    'company_id': company.id,
                    'date_order': data['orden']['creado'], 
                    'gestioo_id': data['orden']['id'],  
                    'client_order_ref': data['orden']['orden_codigo'],
                    'user_id': user_id.id,

                })
                #Creo las lineas de la orden de venta
                self.process_order_lines(order_id, data['orden']['presupuesto_productos'], company=company)
            return json.dumps({'status': 'ok', 'order_id': order_id.id})

    #Creo las lineas de la nota de venta
    def process_order_lines(self, order_id, order_lines, company=None):
        for line in order_lines:
            product_id = False
            if line['producto_id'] != '0':                
                product_id = request.env['product.product'].sudo().search([('gestioo_id', '=', line['producto_id'])], limit=1)
            #Si no existe el id de gestioo busco por el codigo del producto
            if not  product_id and line['codigo'] != '':
                product_id = request.env['product.product'].sudo().search([('default_code', '=', line['codigo'] if line['codigo']!=None else 'No Definido'),
                                                                           ('company_id', '=', company.id)], limit=1)
            if not product_id:
                product_id = request.env['product.product'].sudo().search([('name', '=', line['descripcion'] ),
                                                                           ('company_id', '=', company.id)], limit=1)
                if product_id:
                    product_id.sudo().write({
                        'gestioo_id': line['producto_id'],
                        'taxes_id': [(6, 0, [request.env['account.tax'].sudo().search([('type_tax_use', '=', 'sale'), ('amount', '=', 19), ('company_id', '=', company.id)], limit=1).id])],                        
                        'available_in_pos': True,
                    })
                else:
                    #Si no existe lo creo
                    product_id = request.env['product.product'].sudo().create({
                        'name': line['descripcion'],
                        'default_code': line['codigo'],
                        'detailed_type': 'product',
                        'gestioo_id': line['producto_id'] if line['producto_id'] != '0' else False,
                        'company_id': company.id,
                        'available_in_pos': True,
                    })
                    product_id_w=product_id
                    product_id_w.sudo().product_tmpl_id.sudo().write({
                        'company_id': company.id,
                        'taxes_id': [(6, 0, [request.env['account.tax'].sudo().search([('type_tax_use', '=', 'sale'), ('amount', '=', 19), ('company_id', '=', company.id)], limit=1).id])],                        
                    })
            #Crear la linea de la orden de venta

            request.env['sale.order.line'].sudo().create({
                'order_id': order_id.id,
                'product_id': product_id.id,
                'product_uom_qty': line['cantidad'],
                'price_unit': line['importe'],
                'company_id': company.id,

            })
        return True
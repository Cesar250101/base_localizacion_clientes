# -*- coding: utf-8 -*-

from odoo import models, fields, api



class TopePlanesERP(models.Model):
    _name = 'base_localiazcion_clientes.planes_topes'
    _description = 'Topes para cada plan de ERP'

    name = fields.Char(string='Nombre Plan')    
    max_dtes = fields.Integer(string='Maximo DTEs',default=30)
    max_ventas=fields.Integer(string='Maximo Ventas', default=6000000)



class ResCompany(models.Model):
    _inherit = 'res.company'

    planes_topes_id = fields.Many2one(comodel_name='base_localiazcion_clientes.planes_topes', string='Tipo de Plan')
    integrar_gestioo = fields.Boolean(string='Integrar con Gestioo')
    token_gestioo = fields.Char(string='Token de Gestioo')
    url_webhook_gestioo = fields.Char(string='URL Webhook Gestioo', 
                                      compute='_compute_url_webhook_gestioo',
                                      help='URL que debe configurarse en Gestioo para enviar los datos a Odoo.')

    es_taller = fields.Boolean(string='Es Taller')    

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

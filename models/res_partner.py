from odoo import models, fields, api,SUPERUSER_ID
from odoo.exceptions import UserError


class Partner(models.Model):
    _inherit = 'res.partner'

    gestioo_id = fields.Char(string='GestiOO ID', help='ID del cliente en GestiOO')    
    country_id = fields.Many2one(comodel_name='res.country',
                                 string='Country',
                                 ondelete='restrict',
                                 default=lambda self: self.env['res.country'].search([('name','=','Chile')], limit=1)
                                 )
    company_id = fields.Many2one('res.company', 'Company', index=True, default=lambda self: self.env.company)

    def action_sync_company_from_transactions(self):
        """
        Busca todos los contactos sin compañía y les asigna una basada en sus transacciones.
        Revisa sale.order, purchase.order, account.move y pos.order.
        """
        # Obtenemos partners sin compañía, priorizando los que tienen parent_id para evitar conflictos de jerarquía
        partners = self.search([('company_id', '=', False)], order='parent_id desc, id')
        
        for partner in partners:
            found_company_id = False
            
            # Prioridad 0: Si tiene padre con compañía, esa manda en Odoo
            if partner.parent_id and partner.parent_id.company_id:
                found_company_id = partner.parent_id.company_id.id
            
            if not found_company_id:
                domain = [('partner_id', '=', partner.id), ('company_id', '!=', False)]

                # 1. Sale Order
                if 'sale.order' in self.env:
                    so = self.env['sale.order'].sudo().search(domain, limit=1)
                    if so:
                        found_company_id = so.company_id.id

                # 2. Purchase Order
                if not found_company_id and 'purchase.order' in self.env:
                    po = self.env['purchase.order'].sudo().search(domain, limit=1)
                    if po:
                        found_company_id = po.company_id.id

                # 3. Account Move
                if not found_company_id and 'account.move' in self.env:
                    am = self.env['account.move'].sudo().search(domain, limit=1)
                    if am:
                        found_company_id = am.company_id.id

                # 4. POS Order
                if not found_company_id and 'pos.order' in self.env:
                    pos = self.env['pos.order'].sudo().search(domain, limit=1)
                    if pos:
                        found_company_id = pos.company_id.id

            if found_company_id:
                # Aseguramos compatibilidad con usuarios vinculados (incluyendo inactivos)
                users = self.env['res.users'].sudo().with_context(active_test=False).search([('partner_id', '=', partner.id)])
                for user in users:
                    if found_company_id not in user.company_ids.ids:
                        user.write({'company_ids': [(4, found_company_id)]})
                    
                    # Si el usuario no tiene compañía principal, le asignamos la encontrada
                    if not user.company_id:
                        user.write({'company_id': found_company_id})
                
                # Intentamos actualizar el partner. Si falla por constrains, lo saltamos para no detener el proceso
                try:
                    partner.sudo().write({'company_id': found_company_id})
                    # Forzamos el guardado para que las validaciones se ejecuten ahora y podamos capturar errores
                    partner.flush_recordset(['company_id'])
                except Exception:
                    # Si falla, simplemente continuamos con el siguiente
                    continue
    
    @api.ondelete(at_uninstall=False)
    def _unlink_except_active_pos_session(self):
        company_context=self.env.context.get('allowed_company_ids')
        company=self.env['res.company'].search([('id','=',company_context[0])])
        pos_config_list=[]
        pos_config_ids=self.env['pos.config'].search([('company_id','=',company.id)])
        for i in pos_config_ids:
            pos_config_list.append(i.id)
        running_sessions = self.env['pos.session'].sudo().search([('state', '!=', 'closed'),
                                                                  ('config_id','in',pos_config_list)])
        if running_sessions:
            raise UserError(
                _("You cannot delete contacts while there are active PoS sessions. Close the session(s) %s first.")
                % ", ".join(session.name for session in running_sessions)
            )
        
    #sobre escribo el metodo create para evitar que me indique la el partner_id pertenece a otra compañia
    @api.model
    def create(self, vals):
        if not vals.get('company_id'):
            vals['company_id'] = self.env.company.id
        return super(Partner, self).create(vals)
from odoo import models, fields, api, Command, SUPERUSER_ID, _
from odoo.exceptions import UserError

# Regla multicompañía de contactos (BASELOCCLI-009): además de company_id, un contacto
# es visible en cada compañía de partner_company_ids. Conserva partner_share y los
# contactos sin compañía de la regla original del core (base.res_partner_rule).
PARTNER_COMPANY_RULE_DOMAIN = (
    "['|', ('partner_share', '=', False), "
    "'|', ('company_id', 'in', company_ids + [False]), "
    "('partner_company_ids', 'in', company_ids)]")


class Partner(models.Model):
    _inherit = 'res.partner'

    gestioo_id = fields.Char(string='GestiOO ID', help='ID del cliente en GestiOO')    
    country_id = fields.Many2one(comodel_name='res.country',
                                 string='Country',
                                 ondelete='restrict',
                                 default=lambda self: self.env['res.country'].search([('name','=','Chile')], limit=1)
                                 )
    company_id = fields.Many2one('res.company', 'Company', index=True, default=lambda self: self._default_company_id_bl())
    # Compañías del contacto (BASELOCCLI-009). company_id sigue siendo la compañía
    # principal (Many2one: lo exigen res.partner.bank, check_company y el core);
    # este campo guarda todas las compañías donde el contacto es visible. Sin
    # compañías (vacío) el contacto es global. Invariante: company_id, si está
    # definido, siempre está incluido aquí (ver create/write).
    partner_company_ids = fields.Many2many(
        'res.company', 'res_partner_company_rel', 'partner_id', 'company_id',
        string='Compañías', index=True,
        help='Compañías a las que pertenece el contacto. La compañía principal '
             '(campo Compañía) siempre forma parte de la lista; si se quita de '
             'ella, la principal pasa a otra compañía de la lista.')

    @api.model
    def _update_partner_company_rule(self):
        """Redefine base.res_partner_rule para que considere partner_company_ids.

        El registro del core es noupdate="1", así que un <record> de este módulo no
        lo pisa en un -u: se escribe el dominio desde una <function> (idempotente).
        """
        rule = self.env.ref('base.res_partner_rule', raise_if_not_found=False)
        if rule and rule.domain_force != PARTNER_COMPANY_RULE_DOMAIN:
            rule.sudo().domain_force = PARTNER_COMPANY_RULE_DOMAIN

    @api.model
    def _default_company_id_bl(self):
        # No asignar company_id cuando el partner es la dirección de una compañía
        # nueva (res.company.create() de este módulo setea este contexto): debe
        # quedar en False o falla el check de multi-compañía al crear la empresa.
        if self.env.context.get('creating_from_company'):
            return False
        return self.env.company

    def action_sync_company_from_transactions(self):
        """
        Busca todos los contactos sin compañía y les asigna una basada en sus transacciones.
        Revisa sale.order, purchase.order, account.move y pos.order.
        """
        # Obtenemos partners sin compañía, priorizando los que tienen parent_id para evitar conflictos de jerarquía
        # Los que ya tienen compañías en partner_company_ids no son globales: se omiten.
        partners = self.search([('company_id', '=', False), ('partner_company_ids', '=', False)],
                               order='parent_id desc, id')
        
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
        running_sessions = self.env['pos.session'].sudo().search([
            ('state', '!=', 'closed'),
            ('config_id.company_id', '=', self.env.company.id),
        ])
        if running_sessions:
            raise UserError(
                _("You cannot delete contacts while there are active PoS sessions. Close the session(s) %s first.")
                % ", ".join(session.name for session in running_sessions)
            )
        
    #sobre escribo el metodo create para evitar que me indique la el partner_id pertenece a otra compañia
    @api.model
    def create(self, vals):
        # No forzar company_id cuando el partner se está creando como la dirección
        # de una compañía nueva (res.company.create() setea este contexto): debe
        # quedar en False hasta que la compañía exista, o falla el check de multi-compañía.
        vals = dict(vals)
        if not vals.get('company_id') and not self.env.context.get('creating_from_company'):
            vals['company_id'] = self.env.company.id
        # La compañía principal siempre forma parte de partner_company_ids; si el
        # llamador pasó su propia lista se respeta y se le suma la principal.
        if vals.get('company_id'):
            vals['partner_company_ids'] = list(vals.get('partner_company_ids') or []) + [
                Command.link(vals['company_id'])]
        partner = super(Partner, self).create(vals)
        # La principal puede venir de un default (p. ej. con creating_from_company
        # y l10n_cl_fe/partner_company_default) y no estar en vals.
        partner._link_company_to_partner_companies()
        return partner

    def _link_company_to_partner_companies(self):
        """Agrega company_id a partner_company_ids en los contactos donde falte."""
        for partner in self:
            if partner.company_id and partner.company_id not in partner.partner_company_ids:
                partner.write({'partner_company_ids': [Command.link(partner.company_id.id)]})

    def write(self, vals):
        if 'company_id' not in vals and 'partner_company_ids' not in vals:
            return super(Partner, self).write(vals)
        vals = dict(vals)
        if vals.get('company_id'):
            # Cambiar la principal agrega la nueva a la lista y conserva la anterior.
            vals['partner_company_ids'] = list(vals.get('partner_company_ids') or []) + [
                Command.link(vals['company_id'])]
        elif 'company_id' in vals and 'partner_company_ids' not in vals:
            # Vaciar la compañía principal vuelve global al contacto (como antes de
            # BASELOCCLI-009): sin compañía principal no se conservan las demás.
            vals['partner_company_ids'] = [Command.clear()]
        result = super(Partner, self).write(vals)
        if 'company_id' not in vals:
            self._reconcile_company_with_partner_companies()
        return result

    def _reconcile_company_with_partner_companies(self):
        """Mantiene company_id dentro de partner_company_ids tras editar la lista.

        - Lista vaciada con compañía principal: se repone la principal (para dejar
          al contacto sin compañías hay que vaciar el campo Compañía).
        - Principal quitada de una lista que conserva otras: la principal pasa a la
          de menor id de la lista, de modo que quitar la etiqueta se respeta.
        """
        for partner in self:
            if not partner.company_id or partner.company_id in partner.partner_company_ids:
                continue
            if partner.partner_company_ids:
                partner.write({'company_id': min(partner.partner_company_ids.ids)})
            else:
                partner.write({'partner_company_ids': [Command.link(partner.company_id.id)]})

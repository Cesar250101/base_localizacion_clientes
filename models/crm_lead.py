# -*- coding: utf-8 -*-
from odoo import _, api, fields, models,Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date, formatLang

class Lead(models.Model):
    _inherit = "crm.lead"

    @api.model_create_multi
    def create(self, vals_list):
        company=self.env.context.get('allowed_company_ids',False)[0]
        company=self.env['res.company'].search([('id','=',company)])

        stage_id=self.env['crm.stage'].search([('company_id','=',company.id)],order="sequence",limit=1)
        if not stage_id:
            raise ValidationError(_("No ha definido etapas para el CRM!"))
        vals_list[0]["stage_id"]=int(stage_id.id)
        leads = super(Lead, self).create(vals_list)
        return leads
    
    def write(self, vals):
        company=self.env.context.get('allowed_company_ids',False)[0]
        company=self.env['res.company'].search([('id','=',company)])

        stage_id=self.env['crm.stage'].search([('company_id','=',company.id)],order="sequence",limit=1)
        # if not stage_id:
        #     raise ValidationError(_("No ha definido etapas para el CRM!"))
        if self.stage_id.company_id.id!=company.id:
            vals["stage_id"]=int(stage_id.id)
        leads = super(Lead, self).write(vals)
        return leads    
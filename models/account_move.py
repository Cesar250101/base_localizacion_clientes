from pyparsing import line
from odoo import api, exceptions, fields, models, _
from odoo.tools import pycompat
from datetime import datetime, timedelta
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning


class AccountMove(models.Model):
    _inherit = 'account.move'


    invoice_origin = fields.Char(
        string='Origin',
        tracking=True,
        readonly=False,
        help="El(los) documento(s) que generaron la factura.",
    )
    original_partner_name = fields.Char(
        string='Nombre original',
        readonly=True,
        copy=False,
        help='Nombre del contacto al momento de publicar el documento.',
    )

    def _check_company(self, fnames=None):
        """El contacto del asiento sirve si la compañía del asiento está en
        `partner_company_ids` (BASELOCCLI-010), no solo si es su compañía principal.

        El core exige partner.company_id <= move.company_id; el asiento del pago de una
        factura de B para un contacto con principal A y lista [A, B] fallaba aquí con
        «Empresas incompatibles con los registros». Solo cambia `partner_id`: el resto
        de campos va a super(). Si el contacto no tiene la compañía del asiento, en vez
        de dar el error del core se le agrega a `partner_company_ids`.
        """
        if fnames is None:
            fnames = list(self._fields)
        super()._check_company([name for name in fnames if name != 'partner_id'])
        if 'partner_id' in fnames:
            self.env['res.partner']._link_document_companies(self)

    def _post(self, soft=True):
        posted_moves = super()._post(soft=soft)
        for move in posted_moves.filtered(
            lambda m: (
                m.is_invoice(include_receipts=True)
                and m.company_id.store_original_partner_name
                and not m.original_partner_name
                and m.partner_id
            )
        ):
            move.original_partner_name = move.partner_id.name
        return posted_moves

    @api.depends(
        'partner_id',
        'invoice_source_email',
        'partner_id.display_name',
        'original_partner_name',
    )
    def _compute_invoice_partner_display_info(self):
        super()._compute_invoice_partner_display_info()
        for move in self.filtered('original_partner_name'):
            move.invoice_partner_display_name = move.original_partner_name

    
    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.today()
        first_day = today.replace(day=1)
        last_day = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        domain = [
            ('create_date', '>=', first_day),
            ('create_date', '<=', last_day),
            ('state','=','posted'),
            ('move_type','in',['out_invoice','out_refund','in_invoice','in_refund'])
        ]

        dtes = self.env['account.move'].search(domain)
        count= len(dtes) if dtes else 0,
        amount= sum(dtes.mapped('amount_total')) if dtes else 0,

        if self.env.company.planes_topes_id:
            if self.env.company.planes_topes_id.name in ["Inicia", "Emprende"]:
                if self.env.company.planes_topes_id.name=="Inicia":
                    if amount[0]>self.env.company.planes_topes_id.max_ventas or count[0]>self.env.company.planes_topes_id.max_dtes:
                        raise UserError(
                            'No puede crear una nueva orden ya que ha alcanzado el límite de ' + str(self.env.company.planes_topes_id.max_ventas) + ' de pesos mensual de su plan o ha alcanzado el limite de '
                            + str(self.env.company.planes_topes_id.max_dtes) + ' dtes mensual .Contactese con ventas@method.cl o al telefono +56 9 4233 8955 para actualizar tu plan!'
                        )
                    else:
                        return super().create(vals_list)
                else:
                    if count[0]>self.env.company.planes_topes_id.max_dtes:
                        raise UserError(
                            'No puede crear una nueva factura ya que ha alcanzado el límite de %s nro de dtes de su plan' %
                            self.env.company.planes_topes_id.max_dtes + ' .Contactese con ventas@method.cl o al telefono +56 9 4233 8955 para actualizar tu plan!'
                        )
                    else:
                        return super().create(vals_list)

            else:
                return super().create(vals_list)
        else:
            return super().create(vals_list)

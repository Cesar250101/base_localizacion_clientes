from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestPartnerPosSessionGuard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env['res.company'].create({
            'name': 'Other POS Company',
        })
        cls.user = cls.env['res.users'].with_context(
            no_reset_password=True,
        ).create({
            'name': 'Contact Manager Without POS',
            'login': 'contact_manager_without_pos',
            'email': 'contact_manager_without_pos@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id, cls.other_company.id])],
            'groups_id': [(6, 0, [cls.env.ref('base.group_partner_manager').id])],
        })
        cls.current_company_config = cls.env['pos.config'].with_company(
            cls.company,
        ).create({
            'name': 'Current Company POS Test',
        })
        cls.other_company_config = cls.env['pos.config'].with_company(
            cls.other_company,
        ).create({
            'name': 'Other Company POS Test',
        })

    def _create_partner(self):
        return self.env['res.partner'].sudo().create({
            'name': 'Partner to delete',
            'company_id': self.company.id,
        })

    def _open_session(self, config):
        return self.env['pos.session'].sudo().with_company(
            config.company_id,
        ).create({
            'config_id': config.id,
            'user_id': self.env.ref('base.user_admin').id,
        })

    def _delete_as_contact_manager(self, partner):
        partner.with_user(self.user).with_company(self.company).unlink()

    def test_delete_contact_without_pos_access_when_no_session_is_open(self):
        self.assertFalse(self.user.has_group('point_of_sale.group_pos_user'))

        partner = self._create_partner()
        self._delete_as_contact_manager(partner)

        self.assertFalse(partner.exists())

    def test_delete_contact_when_only_another_company_has_an_open_session(self):
        self._open_session(self.other_company_config)
        partner = self._create_partner()

        self._delete_as_contact_manager(partner)

        self.assertFalse(partner.exists())

    def test_delete_contact_is_blocked_by_open_session_in_current_company(self):
        self._open_session(self.current_company_config)
        partner = self._create_partner()

        with self.assertRaises(UserError):
            self._delete_as_contact_manager(partner)

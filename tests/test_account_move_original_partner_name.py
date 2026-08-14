# -*- coding: utf-8 -*-

import importlib.util
from pathlib import Path

from lxml import etree

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestAccountMoveOriginalPartnerName(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.other_company = cls.company_data_2['company']

    def _create_partner(self, name):
        return self.env['res.partner'].create({
            'name': name,
            'company_id': False,
        })

    def _post_document(self, move_type, company_data, partner):
        move = self.init_invoice(
            move_type,
            partner=partner,
            amounts=[100],
            company=company_data['company'],
        )
        move._post(soft=False)
        return move

    def test_original_partner_name_is_preserved_after_partner_rename(self):
        self.company.store_original_partner_name = True
        partner = self._create_partner('Nombre al publicar')

        move = self._post_document('out_invoice', self.company_data, partner)
        self.assertEqual(move.original_partner_name, 'Nombre al publicar')
        self.assertEqual(move.invoice_partner_display_name, 'Nombre al publicar')

        partner.name = 'Nombre actualizado'
        self.assertEqual(move.original_partner_name, 'Nombre al publicar')
        self.assertEqual(move.invoice_partner_display_name, 'Nombre al publicar')

    def test_original_partner_name_is_not_stored_when_disabled(self):
        self.company.store_original_partner_name = False
        partner = self._create_partner('No almacenar')

        move = self._post_document('out_invoice', self.company_data, partner)

        self.assertFalse(move.original_partner_name)

    def test_original_partner_name_respects_company_setting(self):
        self.company.store_original_partner_name = True
        self.other_company.store_original_partner_name = False
        partner = self._create_partner('Contacto multiempresa')

        enabled_move = self._post_document('out_invoice', self.company_data, partner)
        disabled_move = self._post_document('out_invoice', self.company_data_2, partner)

        self.assertEqual(enabled_move.original_partner_name, partner.name)
        self.assertFalse(disabled_move.original_partner_name)

    def test_configuration_setting_is_related_to_the_active_company(self):
        settings = self.env['res.config.settings'].create({
            'company_id': self.company.id,
        })

        settings.store_original_partner_name = True

        self.assertTrue(self.company.store_original_partner_name)
        self.assertFalse(self.other_company.store_original_partner_name)

    def test_original_partner_name_is_stored_for_all_commercial_documents(self):
        self.company.store_original_partner_name = True

        for move_type in (
            'out_invoice', 'out_refund', 'out_receipt',
            'in_invoice', 'in_refund', 'in_receipt',
        ):
            partner = self._create_partner('Contacto %s' % move_type)
            move = self._post_document(move_type, self.company_data, partner)
            self.assertEqual(move.original_partner_name, partner.name)

    def test_migration_completes_historical_commercial_documents(self):
        self.company.store_original_partner_name = False
        partner = self._create_partner('Nombre histórico')
        move = self._post_document('out_invoice', self.company_data, partner)
        self.assertFalse(move.original_partner_name)

        migration_path = (
            Path(__file__).resolve().parents[1]
            / 'migrations' / '0.4' / 'post-migrate.py'
        )
        spec = importlib.util.spec_from_file_location(
            'base_localizacion_clientes_post_migrate_0_4', migration_path,
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.migrate(self.env.cr, '0.3')
        self.env.invalidate_all()

        self.assertEqual(move.original_partner_name, partner.name)
        self.assertEqual(move.invoice_partner_display_name, partner.name)

    def test_views_include_original_partner_name(self):
        for view_xmlid, view_type, field_name in (
            ('account.view_move_form', 'form', 'invoice_partner_display_name'),
            ('account.view_move_tree', 'tree', 'original_partner_name'),
            ('account.view_invoice_tree', 'tree', 'original_partner_name'),
        ):
            view = self.env['account.move'].get_view(
                view_id=self.env.ref(view_xmlid).id,
                view_type=view_type,
            )
            arch = etree.fromstring(view['arch'])
            self.assertTrue(
                arch.xpath("//field[@name='%s']" % field_name),
                'El campo %s debe estar presente en la vista %s.' % (
                    field_name, view_xmlid,
                ),
            )

        settings_view = self.env['res.config.settings'].get_view(
            view_id=self.env.ref('account.res_config_settings_view_form').id,
            view_type='form',
        )
        settings_arch = etree.fromstring(settings_view['arch'])
        self.assertTrue(
            settings_arch.xpath("//field[@name='store_original_partner_name']"),
            'La opción debe estar presente en Configuración de Contabilidad.',
        )

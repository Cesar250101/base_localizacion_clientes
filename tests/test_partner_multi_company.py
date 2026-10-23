# -*- coding: utf-8 -*-
# BASELOCCLI-009: un contacto puede pertenecer a varias compañías
# (res.partner.partner_company_ids); company_id sigue siendo la principal.

import importlib.util
import json
from unittest.mock import patch
from xml.etree import ElementTree

from odoo.exceptions import AccessError
from odoo.modules.module import get_module_path, load_information_from_description_file
from odoo.tests.common import HttpCase, TransactionCase
from odoo.tools.safe_eval import safe_eval

MODULE = 'base_localizacion_clientes'


def _module_file(*parts):
    return '/'.join([get_module_path(MODULE)] + list(parts))


def _xml_record_field(relative_path, record_id, field_name):
    """Texto del campo `field_name` del <record id=record_id> de un XML del módulo."""
    tree = ElementTree.parse(_module_file(*relative_path.split('/')))
    for record in tree.iter('record'):
        if record.get('id') == record_id:
            for field in record.iter('field'):
                if field.get('name') == field_name:
                    return field.text
    raise AssertionError('No se encontró %s.%s en %s' % (record_id, field_name, relative_path))


class PartnerMultiCompanyCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.company_a = Company.create({'name': 'Multi Partner A'})
        cls.company_b = Company.create({'name': 'Multi Partner B'})
        cls.company_c = Company.create({'name': 'Multi Partner C'})
        cls.user_a = cls._create_user('multi_partner_user_a', cls.company_a)
        cls.user_b = cls._create_user('multi_partner_user_b', cls.company_b)
        cls.user_ab = cls._create_user('multi_partner_user_ab', cls.company_a | cls.company_b)

    @classmethod
    def _create_user(cls, login, companies):
        groups = [cls.env.ref('base.group_user').id]
        if len(companies) > 1:
            groups.append(cls.env.ref('base.group_multi_company').id)
        return cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': login,
            'login': login,
            'email': '%s@example.com' % login,
            'company_id': companies[0].id,
            'company_ids': [(6, 0, companies.ids)],
            'groups_id': [(6, 0, groups)],
        })

    def _partner(self, name, company=None, companies=None, **extra):
        vals = dict(name=name, **extra)
        if company is not None:
            vals['company_id'] = company.id
        if companies is not None:
            vals['partner_company_ids'] = [(6, 0, companies.ids)]
        return self.env['res.partner'].create(vals)


class TestPartnerCompanyInvariant(PartnerMultiCompanyCase):
    """Criterios 1 y 2: lista de compañías e invariante company_id ⊆ partner_company_ids."""

    def test_partner_accepts_several_companies(self):
        partner = self._partner(
            'Multi', self.company_a, self.company_a | self.company_b | self.company_c)
        self.assertEqual(partner.company_id, self.company_a)
        self.assertEqual(
            partner.partner_company_ids, self.company_a | self.company_b | self.company_c)

    def test_form_shows_companies_as_tags(self):
        view = self.env['res.partner'].with_user(self.user_ab).get_view(view_type='form')
        form = ElementTree.fromstring(view['arch'])
        fields = [f for f in form.iter('field') if f.get('name') == 'partner_company_ids']
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].get('widget'), 'many2many_tags')

    def test_create_adds_main_company_to_list(self):
        partner = self._partner('Solo principal', self.company_a)
        self.assertEqual(partner.partner_company_ids, self.company_a)

    def test_create_without_company_uses_active_company(self):
        partner = self.env['res.partner'].with_company(self.company_b).create({'name': 'Activa'})
        self.assertEqual(partner.company_id, self.company_b)
        self.assertEqual(partner.partner_company_ids, self.company_b)

    def test_create_respects_explicit_list_and_adds_main(self):
        partner = self._partner('Lista', self.company_a, self.company_b)
        self.assertEqual(partner.partner_company_ids, self.company_a | self.company_b)

    def test_create_with_partner_company_default_context_keeps_invariant(self):
        # partner_company_default (si está instalado) también redefine el default
        # de company_id y se activa en tests con este contexto.
        partners = self.env['res.partner'].with_context(
            test_partner_company_default=True).with_company(self.company_c).create([
                {'name': 'Default A'},
                {'name': 'Default B', 'company_id': self.company_b.id},
            ])
        self.assertEqual(partners[0].company_id, self.company_c)
        self.assertEqual(partners[0].partner_company_ids, self.company_c)
        self.assertEqual(partners[1].partner_company_ids, self.company_b)

    def test_create_links_company_that_comes_from_a_default(self):
        # company_id llega por un default (no está en vals) y con creating_from_company
        # create no lo fuerza: la reparación posterior al create debe agregarlo a la lista.
        partner = self.env['res.partner'].with_context(
            creating_from_company=True, default_company_id=self.company_b.id,
        ).create({'name': 'Principal por default'})
        self.assertEqual(partner.company_id, self.company_b)
        self.assertEqual(partner.partner_company_ids, self.company_b)

    def test_create_from_company_keeps_it_global(self):
        partner = self.env['res.partner'].with_context(creating_from_company=True).create(
            {'name': 'Dirección de compañía nueva'})
        self.assertFalse(partner.company_id)
        self.assertFalse(partner.partner_company_ids)

    def test_create_batch_syncs_each_partner(self):
        partners = self.env['res.partner'].create([
            {'name': 'Lote A', 'company_id': self.company_a.id},
            {'name': 'Lote B', 'company_id': self.company_b.id,
             'partner_company_ids': [(6, 0, self.company_c.ids)]},
        ])
        self.assertEqual(partners[0].partner_company_ids, self.company_a)
        self.assertEqual(partners[1].partner_company_ids, self.company_b | self.company_c)

    def test_write_company_adds_new_and_keeps_previous(self):
        partner = self._partner('Cambio', self.company_a)
        partner.write({'company_id': self.company_b.id})
        self.assertEqual(partner.company_id, self.company_b)
        self.assertEqual(partner.partner_company_ids, self.company_a | self.company_b)

    def test_write_list_with_new_company_keeps_main(self):
        partner = self._partner('Lista nueva', self.company_a)
        partner.write({'partner_company_ids': [(4, self.company_b.id)]})
        self.assertEqual(partner.company_id, self.company_a)
        self.assertEqual(partner.partner_company_ids, self.company_a | self.company_b)

    def test_write_emptied_list_restores_main(self):
        partner = self._partner('Vaciada', self.company_a, self.company_b)
        partner.write({'partner_company_ids': [(5, 0, 0)]})
        self.assertEqual(partner.company_id, self.company_a)
        self.assertEqual(partner.partner_company_ids, self.company_a)

    def test_write_removing_main_moves_main_to_remaining(self):
        partner = self._partner('Quitar principal', self.company_a, self.company_b | self.company_c)
        partner.write({'partner_company_ids': [(3, self.company_a.id)]})
        self.assertEqual(partner.company_id, self.company_b)
        self.assertEqual(partner.partner_company_ids, self.company_b | self.company_c)

    def test_write_clearing_main_makes_partner_global(self):
        partner = self._partner('Global', self.company_a, self.company_b)
        partner.write({'company_id': False})
        self.assertFalse(partner.company_id)
        self.assertFalse(partner.partner_company_ids)

    def test_write_both_fields_in_one_call(self):
        partner = self._partner('Ambos', self.company_a)
        partner.write({
            'company_id': self.company_b.id,
            'partner_company_ids': [(6, 0, self.company_c.ids)],
        })
        self.assertEqual(partner.company_id, self.company_b)
        self.assertEqual(partner.partner_company_ids, self.company_b | self.company_c)

    def test_write_company_on_recordset(self):
        partners = self._partner('Uno', self.company_a) | self._partner('Dos', self.company_c)
        partners.write({'company_id': self.company_b.id})
        for partner in partners:
            self.assertIn(self.company_b, partner.partner_company_ids)
        self.assertEqual(partners[0].partner_company_ids, self.company_a | self.company_b)
        self.assertEqual(partners[1].partner_company_ids, self.company_c | self.company_b)

    def test_company_field_keeps_many2one(self):
        field = self.env['res.partner']._fields['company_id']
        self.assertEqual(field.type, 'many2one')
        self.assertTrue(field.index)


class TestPartnerCompanyDomains(PartnerMultiCompanyCase):
    """Criterios 3 y 4: dominios de acciones, filtro y _sync_contacts_action_domain."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_ab = cls._partner_cls('Contacto A+B', cls.company_a, cls.company_a | cls.company_b)
        cls.partner_a = cls._partner_cls('Contacto solo A', cls.company_a)
        cls.partner_b = cls._partner_cls('Contacto solo B', cls.company_b)
        cls.partner_global = cls.env['res.partner'].with_context(creating_from_company=True).create(
            {'name': 'Contacto global'})
        cls.partners = cls.partner_ab | cls.partner_a | cls.partner_b | cls.partner_global

    @classmethod
    def _partner_cls(cls, name, company, companies=None):
        return cls.env['res.partner'].create({
            'name': name,
            'company_id': company.id,
            'partner_company_ids': [(6, 0, (companies or company).ids)],
        })

    def _search(self, domain_text, company):
        domain = safe_eval(domain_text, {'allowed_company_ids': [company.id]})
        return self.env['res.partner'].search(domain + [('id', 'in', self.partners.ids)])

    def test_contacts_action_domain_lists_partner_with_active_company_in_list(self):
        domain_text = _xml_record_field(
            'views/res_partner.xml', 'contacts.action_contacts', 'domain')
        self.assertIn('partner_company_ids', domain_text)
        self.assertNotIn("('company_id'", domain_text)
        found = self._search(domain_text, self.company_b)
        self.assertEqual(found, self.partner_ab | self.partner_b)
        found = self._search(domain_text, self.company_a)
        self.assertEqual(found, self.partner_ab | self.partner_a)

    def test_contacts_action_keeps_default_filter(self):
        context = _xml_record_field(
            'views/res_partner.xml', 'contacts.action_contacts', 'context')
        self.assertEqual(safe_eval(context).get('search_default_company_contacts'), 1)
        action = self.env.ref('contacts.action_contacts')
        self.assertEqual(safe_eval(action.context).get('search_default_company_contacts'), 1)

    def test_customer_action_domain_includes_global_and_multicompany(self):
        for domain_text in (
            _xml_record_field('views/res_partner.xml', 'account.res_partner_action_customer', 'domain'),
            self.env.ref('account.res_partner_action_customer').domain,
        ):
            self.assertIn('partner_company_ids', domain_text)
            self.assertNotIn("('company_id'", domain_text)
            found = self._search(domain_text, self.company_b)
            self.assertEqual(found, self.partner_ab | self.partner_b | self.partner_global)

    def test_company_contacts_filter_uses_partner_company_ids(self):
        view = self.env.ref('%s.view_res_partner_filter' % MODULE)
        arch = ElementTree.fromstring(view.arch_db)
        filters = [f for f in arch.iter('filter') if f.get('name') == 'company_contacts']
        self.assertEqual(len(filters), 1)
        domain_text = filters[0].get('domain')
        self.assertIn('partner_company_ids', domain_text)
        self.assertNotIn("('company_id'", domain_text)
        found = self._search(domain_text, self.company_b)
        self.assertEqual(found, self.partner_ab | self.partner_b | self.partner_global)

    def test_sync_contacts_action_domain_single_company_is_new_and_idempotent(self):
        action = self.env.ref('contacts.action_contacts')
        Company = type(self.env['res.company'])
        with patch.object(Company, 'search', return_value=self.company_a):
            self.env['res.company']._sync_contacts_action_domain()
            first = action.domain
            self.assertIn('partner_company_ids', first)
            self.assertNotIn("('company_id'", first)
            self.assertEqual(
                safe_eval(first), [
                    '|',
                    ('partner_company_ids', 'in', [self.company_a.id]),
                    ('partner_company_ids', '=', False),
                ])
            # Segunda ejecución: el dominio ya está al día, no debe escribir nada.
            Action = type(action)
            with patch.object(Action, 'write', autospec=True, side_effect=Action.write) as write:
                self.env['res.company']._sync_contacts_action_domain()
            self.assertEqual(write.call_count, 0)
            self.assertEqual(action.domain, first)

    def test_sync_contacts_action_domain_leaves_multicompany_domain(self):
        action = self.env.ref('contacts.action_contacts')
        action.domain = "[('partner_company_ids', 'in', [allowed_company_ids[0]])]"
        self.env['res.company']._sync_contacts_action_domain()
        self.assertEqual(
            action.domain, "[('partner_company_ids', 'in', [allowed_company_ids[0]])]")


class TestPartnerCompanyRule(PartnerMultiCompanyCase):
    """Criterio 5: base.res_partner_rule también mira partner_company_ids."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        cls.partner_ab = Partner.create({
            'name': 'Regla A+B', 'company_id': cls.company_a.id,
            'partner_company_ids': [(6, 0, (cls.company_a | cls.company_b).ids)]})
        cls.partner_a = Partner.create({'name': 'Regla solo A', 'company_id': cls.company_a.id})
        cls.partner_global = Partner.with_context(creating_from_company=True).create(
            {'name': 'Regla global'})

    def _visible(self, user, company, partners):
        env_partners = partners.with_user(user).with_context(allowed_company_ids=[company.id])
        return env_partners.search([('id', 'in', partners.ids)])

    def test_rule_domain_is_redefined(self):
        rule = self.env.ref('base.res_partner_rule')
        self.assertIn('partner_company_ids', rule.domain_force)
        self.assertIn('partner_share', rule.domain_force)

    def test_update_function_restores_rule_and_is_idempotent(self):
        rule = self.env.ref('base.res_partner_rule')
        # Dominio original del core: oculta al usuario de B el contacto A+B.
        rule.domain_force = (
            "['|', ('partner_share', '=', False), ('company_id', 'in', company_ids + [False])]")
        partners = self.partner_ab | self.partner_a
        self.assertFalse(self._visible(self.user_b, self.company_b, partners))
        self.env['res.partner']._update_partner_company_rule()
        self.assertIn('partner_company_ids', rule.domain_force)
        self.assertEqual(self._visible(self.user_b, self.company_b, partners), self.partner_ab)
        domain = rule.domain_force
        self.env['res.partner']._update_partner_company_rule()
        self.assertEqual(rule.domain_force, domain)

    def test_user_b_reads_multicompany_partner_but_not_partner_only_in_a(self):
        partners = self.partner_ab | self.partner_a
        self.assertEqual(self._visible(self.user_b, self.company_b, partners), self.partner_ab)
        self.assertTrue(
            self.partner_ab.with_user(self.user_b).with_context(
                allowed_company_ids=[self.company_b.id]).read(['name']))
        with self.assertRaises(AccessError):
            self.partner_a.with_user(self.user_b).with_context(
                allowed_company_ids=[self.company_b.id]).read(['name'])

    def test_user_a_reads_both_partners(self):
        partners = self.partner_ab | self.partner_a
        self.assertEqual(self._visible(self.user_a, self.company_a, partners), partners)

    def test_user_with_both_companies_sees_all_or_active_company(self):
        partners = self.partner_ab | self.partner_a
        env_both = partners.with_user(self.user_ab).with_context(
            allowed_company_ids=[self.company_a.id, self.company_b.id])
        self.assertEqual(env_both.search([('id', 'in', partners.ids)]), partners)
        self.assertEqual(self._visible(self.user_ab, self.company_b, partners), self.partner_ab)

    def test_global_partner_stays_visible(self):
        self.assertEqual(
            self._visible(self.user_b, self.company_b, self.partner_global), self.partner_global)

    def test_partner_of_internal_user_stays_visible_in_other_company(self):
        # partner_share = False: siempre visible, sin importar la compañía.
        partner_user_a = self.user_a.partner_id
        self.assertFalse(partner_user_a.partner_share)
        self.assertEqual(
            self._visible(self.user_b, self.company_b, partner_user_a), partner_user_a)


class TestPartnerCompanyMigration(PartnerMultiCompanyCase):
    """Criterio 6: la migración 0.8 copia company_id a la lista, sin duplicar."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        spec = importlib.util.spec_from_file_location(
            'bl_post_migrate_0_8', _module_file('migrations', '0.8', 'post-migrate.py'))
        cls.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.migration)

    def _rel_count(self, partner):
        self.env.cr.execute(
            "SELECT company_id FROM res_partner_company_rel WHERE partner_id = %s ORDER BY company_id",
            (partner.id,))
        return [row[0] for row in self.env.cr.fetchall()]

    def test_migration_fills_list_from_company_id_and_is_idempotent(self):
        partner = self._partner('Migrar', self.company_a)
        no_company = self.env['res.partner'].with_context(creating_from_company=True).create(
            {'name': 'Migrar global'})
        # Estado previo a la migración: company_id definido, lista vacía.
        self.env.cr.execute(
            "DELETE FROM res_partner_company_rel WHERE partner_id IN %s",
            (tuple((partner | no_company).ids),))
        self.env.invalidate_all()
        self.assertEqual(self._rel_count(partner), [])

        self.migration.migrate(self.env.cr, '0.7')
        self.assertEqual(self._rel_count(partner), [self.company_a.id])
        self.assertEqual(self._rel_count(no_company), [])

        self.env.cr.execute("SELECT count(*) FROM res_partner_company_rel")
        total = self.env.cr.fetchone()[0]
        self.migration.migrate(self.env.cr, '0.7')
        self.env.cr.execute("SELECT count(*) FROM res_partner_company_rel")
        self.assertEqual(self.env.cr.fetchone()[0], total)
        self.assertEqual(self._rel_count(partner), [self.company_a.id])

    def test_migration_and_post_init_hook_share_one_function(self):
        package = importlib.import_module('odoo.addons.%s' % MODULE)
        self.assertIs(
            self.migration.populate_partner_companies, package.hooks.populate_partner_companies)

    def test_migration_keeps_extra_companies(self):
        partner = self._partner('Migrar extra', self.company_a, self.company_b)
        self.env.cr.execute(
            "DELETE FROM res_partner_company_rel WHERE partner_id = %s AND company_id = %s",
            (partner.id, self.company_a.id))
        self.migration.migrate(self.env.cr, '0.7')
        self.assertEqual(
            self._rel_count(partner), sorted([self.company_a.id, self.company_b.id]))


class TestPartnerCompanyMerge(PartnerMultiCompanyCase):
    """Criterio 7: el asistente de fusión une las compañías de los contactos."""

    def _wizard(self, company=None):
        wizard = self.env['base.partner.merge.automatic.wizard'].create({})
        return wizard.with_company(company) if company else wizard

    def test_merge_unions_companies_into_destination(self):
        dst = self._partner('Fusión destino', self.company_a)
        src = self._partner('Fusión origen', self.company_b, self.company_b | self.company_c)
        self._wizard()._merge([dst.id, src.id], dst_partner=dst)
        self.assertFalse(src.exists())
        self.assertEqual(dst.partner_company_ids, self.company_a | self.company_b | self.company_c)

    def test_merge_unions_main_company_missing_from_source_list(self):
        # Contacto heredado con company_id sin su fila en la lista: la unión
        # debe incluir igualmente su compañía principal.
        dst = self._partner('Fusión destino 2', self.company_a)
        src = self._partner('Fusión origen 2', self.company_b)
        self.env.cr.execute(
            "DELETE FROM res_partner_company_rel WHERE partner_id = %s", (src.id,))
        self.env.invalidate_all()
        self.assertFalse(src.partner_company_ids)
        self._wizard()._merge([dst.id, src.id], dst_partner=dst)
        self.assertEqual(dst.partner_company_ids, self.company_a | self.company_b)

    def test_merge_destination_without_company_takes_source_company(self):
        dst = self.env['res.partner'].with_context(creating_from_company=True).create(
            {'name': 'Fusión global'})
        src = self._partner('Fusión origen 3', self.company_b, self.company_b | self.company_c)
        self._wizard()._merge([dst.id, src.id], dst_partner=dst)
        self.assertEqual(dst.company_id, self.company_b)
        self.assertEqual(dst.partner_company_ids, self.company_b | self.company_c)

    def test_duplicates_are_scoped_to_companies_of_the_active_company(self):
        in_b = self._partner('Duplicado', self.company_a, self.company_a | self.company_b)
        also_in_b = self._partner('Duplicado', self.company_b)
        only_a = self._partner('Duplicado', self.company_a)
        wizard = self._wizard(self.company_b)
        query = "SELECT 'k', ARRAY[%s, %s]::int[]" % (in_b.id, also_in_b.id)
        wizard._process_query_by_company(query)
        self.assertEqual(wizard.number_group, 1)
        wizard = self._wizard(self.company_b)
        wizard._process_query_by_company("SELECT 'k', ARRAY[%s, %s]::int[]" % (in_b.id, only_a.id))
        self.assertEqual(wizard.number_group, 0)


class TestPartnerCompanyMatchPoint(PartnerMultiCompanyCase):
    """Criterio 7: la búsqueda de cliente de MatchPoint ve contactos multicompañía."""

    def _find(self, company, **sale):
        return self.env['pos.order']._matchpoint_find_partner(company, sale)

    def test_find_by_name_returns_multicompany_partner_of_the_company(self):
        partner = self._partner('Cliente MatchPoint', self.company_a, self.company_a | self.company_b)
        self.assertEqual(self._find(self.company_b, customerName='cliente matchpoint'), partner)

    def test_find_by_name_ignores_partner_only_in_other_company(self):
        partner = self._partner('Cliente solo A', self.company_a)
        found = self._find(self.company_b, customerName='Cliente solo A')
        self.assertNotEqual(found, partner)
        self.assertEqual(found.company_id, self.company_b)
        self.assertEqual(found.partner_company_ids, self.company_b)

    def test_find_by_vat_returns_multicompany_partner(self):
        partner = self._partner('Cliente con RUT', self.company_a, self.company_a | self.company_b)
        partner.vat = 'CL111111111'
        # l10n_cl_fe puede reformatear el RUT al guardarlo: se busca por lo almacenado.
        self.assertTrue(partner.vat)
        self.assertEqual(self._find(self.company_b, customerIdent=partner.vat), partner)

    def test_find_global_partner(self):
        partner = self.env['res.partner'].with_context(creating_from_company=True).create(
            {'name': 'Cliente global MatchPoint'})
        self.assertEqual(self._find(self.company_b, customerName='Cliente global MatchPoint'), partner)


class TestPartnerCompanyTransactionSync(PartnerMultiCompanyCase):
    """Criterio 7: action_sync_company_from_transactions respeta la lista."""

    def test_sync_skips_partner_that_already_has_companies(self):
        # El padre tiene compañía: sin la exclusión el hijo la heredaría.
        parent = self._partner('Sync padre 2', self.company_c)
        partner = self.env['res.partner'].create({'name': 'Sync con lista', 'parent_id': parent.id})
        partner.write({'company_id': False})
        partner.write({'partner_company_ids': [(6, 0, self.company_b.ids)]})
        self.assertFalse(partner.company_id)
        self.env['res.partner'].action_sync_company_from_transactions()
        self.assertFalse(partner.company_id)
        self.assertEqual(partner.partner_company_ids, self.company_b)

    def test_sync_assigns_company_from_transaction_and_updates_list(self):
        partner = self.env['res.partner'].with_context(creating_from_company=True).create(
            {'name': 'Sync sin lista'})
        self.assertFalse(partner.partner_company_ids)
        parent = self._partner('Sync padre', self.company_c)
        partner.parent_id = parent
        self.env['res.partner'].action_sync_company_from_transactions()
        self.assertEqual(partner.company_id, self.company_c)
        self.assertIn(self.company_c, partner.partner_company_ids)


class TestPartnerCompanyGestiooWebhook(HttpCase):
    """Criterio 7: el webhook GestiOO funciona con contactos multicompañía.

    El webhook busca por compañía principal (company_id) porque sale.order tiene
    check_company: un contacto con otra compañía principal no se puede usar aunque
    la compañía esté en su lista.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.company_a = Company.create({'name': 'Gestioo A'})
        cls.company_b = Company.create({
            'name': 'Gestioo B', 'integrar_gestioo': True, 'token_gestioo': 'tok-gestioo-multi-b'})
        cls.partner_ba = cls.env['res.partner'].create({
            'name': 'Gestioo B+A', 'company_id': cls.company_b.id, 'gestioo_id': 'G-BA',
            'partner_company_ids': [(6, 0, (cls.company_a | cls.company_b).ids)]})
        cls.partner_ab = cls.env['res.partner'].create({
            'name': 'Gestioo A+B', 'company_id': cls.company_a.id, 'gestioo_id': 'G-AB',
            'partner_company_ids': [(6, 0, (cls.company_a | cls.company_b).ids)]})

    def _orden(self, cliente_id, orden_id):
        return {'orden': {
            'area_nombre': 'Salida',
            'cliente_id': cliente_id,
            'cliente_dni': '11111111-1',
            'cliente_nombre': 'Cliente',
            'cliente_apellido': 'Gestioo',
            'cliente_direccion': 'Calle 1',
            'cliente_telefono': '123',
            'cliente_correo': 'cliente@example.com',
            'id': orden_id,
            'responsable_id': 'R-%s' % orden_id,
            'responsable_nombre': 'Responsable',
            'responsable_apellido': orden_id,
            'orden_numeracion': 'GST-%s' % orden_id,
            'orden_codigo': 'COD-%s' % orden_id,
            'creado': '2026-01-01 10:00:00',
            'presupuesto_productos': [],
        }}

    def _post(self, payload):
        response = self.url_open(
            '/base_localizacion_clientes/gestioo?token=tok-gestioo-multi-b',
            data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 200, response.text)
        return json.loads(response.text)

    def test_webhook_reuses_multicompany_partner_with_matching_main_company(self):
        result = self._post(self._orden('G-BA', 'O-BA'))
        order = self.env['sale.order'].browse(result['order_id'])
        self.assertEqual(order.company_id, self.company_b)
        self.assertEqual(order.partner_id, self.partner_ba)
        self.assertEqual(self.partner_ba.partner_company_ids, self.company_a | self.company_b)

    def test_webhook_creates_partner_when_main_company_is_other(self):
        result = self._post(self._orden('G-AB', 'O-AB'))
        order = self.env['sale.order'].browse(result['order_id'])
        self.assertNotEqual(order.partner_id, self.partner_ab)
        self.assertEqual(order.partner_id.company_id, self.company_b)
        self.assertEqual(order.partner_id.partner_company_ids, self.company_b)


class TestPartnerCompanyHooks(PartnerMultiCompanyCase):
    """post_init_hook (-i) y uninstall_hook, declarados en el manifiesto."""

    CORE_RULE = "['|', ('partner_share', '=', False), ('company_id', 'in', company_ids + [False])]"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.package = importlib.import_module('odoo.addons.%s' % MODULE)

    def _rel_companies(self, partner):
        self.env.cr.execute(
            "SELECT company_id FROM res_partner_company_rel WHERE partner_id = %s ORDER BY company_id",
            (partner.id,))
        return [row[0] for row in self.env.cr.fetchall()]

    def test_hooks_are_declared_in_manifest_and_importable(self):
        info = load_information_from_description_file(MODULE)
        for key in ('post_init_hook', 'uninstall_hook'):
            self.assertEqual(info.get(key), key)
            self.assertTrue(callable(getattr(self.package, key, None)), key)

    def test_post_init_hook_populates_list_on_database_with_contacts(self):
        # Base con contactos previos a la instalación: lista vacía.
        partner = self._partner('Hook A', self.company_a)
        other = self._partner('Hook A+B', self.company_a, self.company_a | self.company_b)
        self.env.cr.execute(
            "DELETE FROM res_partner_company_rel WHERE partner_id IN %s", (tuple((partner | other).ids),))
        self.env.invalidate_all()
        self.package.post_init_hook(self.env.cr, self.registry)
        self.assertEqual(self._rel_companies(partner), [self.company_a.id])
        self.assertEqual(self._rel_companies(other), [self.company_a.id])
        self.env.invalidate_all()
        self.assertEqual(partner.partner_company_ids, self.company_a)
        # Idempotente: no duplica filas.
        self.env.cr.execute("SELECT count(*) FROM res_partner_company_rel")
        total = self.env.cr.fetchone()[0]
        self.package.post_init_hook(self.env.cr, self.registry)
        self.env.cr.execute("SELECT count(*) FROM res_partner_company_rel")
        self.assertEqual(self.env.cr.fetchone()[0], total)

    def test_uninstall_hook_restores_core_rule_and_search_works(self):
        rule = self.env.ref('base.res_partner_rule')
        self.assertIn('partner_company_ids', rule.domain_force)
        self.package.uninstall_hook(self.env.cr, self.registry)
        rule.invalidate_recordset()
        self.assertEqual(rule.domain_force, self.CORE_RULE)
        self.assertNotIn('partner_company_ids', rule.domain_force)
        partner = self._partner('Hook desinstalar', self.company_b)
        found = self.env['res.partner'].with_user(self.user_b).with_context(
            allowed_company_ids=[self.company_b.id]).search([('id', '=', partner.id)])
        self.assertEqual(found, partner)

    def test_uninstall_hook_is_idempotent(self):
        self.package.uninstall_hook(self.env.cr, self.registry)
        IrRule = type(self.env['ir.rule'])
        Action = type(self.env['ir.actions.act_window'])
        with patch.object(IrRule, 'write', autospec=True, side_effect=IrRule.write) as rule_write, \
                patch.object(Action, 'write', autospec=True, side_effect=Action.write) as action_write:
            self.package.uninstall_hook(self.env.cr, self.registry)
        self.assertEqual(rule_write.call_count, 0)
        self.assertEqual(action_write.call_count, 0)

    def test_uninstall_hook_cleans_core_actions(self):
        contacts = self.env.ref('contacts.action_contacts')
        customers = self.env.ref('account.res_partner_action_customer')
        contacts.write({
            'domain': "[('partner_company_ids', 'in', [allowed_company_ids[0]])]",
            'context': "{'search_default_company_contacts': 1}",
        })
        customers.domain = (
            "['|',('partner_company_ids', 'in', [allowed_company_ids[0]]),"
            "('partner_company_ids', '=', False)]")
        self.package.uninstall_hook(self.env.cr, self.registry)
        self.assertFalse(contacts.domain)
        self.assertEqual(safe_eval(contacts.context), {'default_is_company': True})
        self.assertFalse(customers.domain)


class TestPartnerCompanySupplierinfo(PartnerMultiCompanyCase):
    """product.supplierinfo.partner_id: dominio por partner_company_ids."""

    def _domain(self, company):
        text = self.env['product.supplierinfo']._fields['partner_id'].domain
        return safe_eval(text, {'company_id': company.id if company else False})

    def test_domain_lists_partners_of_the_line_company(self):
        partner_ab = self._partner('Proveedor A+B', self.company_a, self.company_a | self.company_b)
        partner_a = self._partner('Proveedor solo A', self.company_a)
        partner_global = self.env['res.partner'].with_context(creating_from_company=True).create(
            {'name': 'Proveedor global'})
        partners = partner_ab | partner_a | partner_global
        Partner = self.env['res.partner']
        self.assertEqual(
            Partner.search(self._domain(self.company_b) + [('id', 'in', partners.ids)]), partner_ab)
        self.assertEqual(
            Partner.search(self._domain(self.company_a) + [('id', 'in', partners.ids)]),
            partner_ab | partner_a)
        self.assertEqual(
            Partner.search(self._domain(False) + [('id', 'in', partners.ids)]), partner_global)

    def test_supplierinfo_in_b_with_partner_of_main_company_a_saves(self):
        # product.supplierinfo no tiene _check_company_auto: guardar no valida la
        # compañía principal del contacto.
        partner = self._partner('Proveedor A', self.company_a, self.company_a | self.company_b)
        template = self.env['product.template'].create({'name': 'Producto proveedor'})
        info = self.env['product.supplierinfo'].create({
            'partner_id': partner.id, 'product_tmpl_id': template.id,
            'company_id': self.company_b.id, 'price': 1.0})
        self.assertEqual(info.partner_id, partner)

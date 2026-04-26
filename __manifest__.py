# -*- coding: utf-8 -*-
{
    'name': "base_localizacion_clientes",

    'summary': """
                    Localizacion de clientes method
                """,

    'description': """
        Aqui van a ir todas las localizaciones de la base de datos 
        Clientes method
        Inventario:
            -agrega company_id a las categorias
    """,

    'author': "Method",
    'website': "https://www.method.cl",
    'icon': 'base_localizacion_clientes/static/description/icon.png',
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base',
    'stock',
    'product',
    'point_of_sale',
    'crm',
    'account',
    'project',
    'hr_timesheet',
    'sale',
    'purchase',
    'repair'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/planes_topes.xml',
        'views/res_partner.xml',
        'views/templates.xml',
        'views/product_category.xml',
        'views/pos_category.xml',
        'views/plates_topes.xml',
        'views/res_company.xml',
        'views/account_move.xml',
        'views/account_group_views.xml',
        'views/menu_inherit.xml',
        'views/pos_config_view.xml',
        'views/repair_order.xml',
        # 'views/purchase_order_views.xml',
        'views/import_purchase_lines_wizard_views.xml',
        'report/report_saleorder_document.xml',

    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'base_localizacion_clientes/static/src/js/pos_category_filter.js',
        ],
    },   
}

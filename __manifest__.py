# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Outsourcing',
    # 'version': '1.1',
    # 'website': 'https://www.odoo.com/page/outsourcing-management',
    # 'category': 'Operations/outsourcing',
    # 'sequence': 10,
    # 'summary': 'Organize and schedule your outsourcings ',
    'depends': [
        'analytic',
        'base_setup',
        'mail',
        'portal',
        'rating',
        'resource',
        'web',
        'web_tour',
        'digest',
    ],
    'description': "",
    'data': [
        'security/outsourcing_security.xml',
        'security/ir.model.access.csv',
        'report/outsourcing_report_views.xml',
        'views/analytic_views.xml',
        'views/digest_views.xml',
        'views/rating_views.xml',
        'views/outsourcing_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/mail_activity_views.xml',
        'views/outsourcing_assets.xml',
        'views/outsourcing_portal_templates.xml',
        'views/outsourcing_rating_templates.xml',
        'data/digest_data.xml',
        'data/outsourcing_mail_template_data.xml',
        'data/outsourcing_data.xml',
    ],
    # 'demo': ['data/outsourcing_demo.xml'],
    'test': [
    ],
    # 'installable': True,
    # 'auto_install': False,
    # 'application': True,
}

#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

{
    'name': 'Electrical customer activity',
    'version': '0.1',
    'category': 'Report',
    'description': '''  
        Partner activity for invoice
           - Stock document for material      
           - List of intervent
           - Account contract opened
        ''',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'account',
        'analytic',
        'product',
        'metel_pricelist',
        'electrical_account_expence',

        # Stock operation:
        'electrical_l10n_it_ddt',

        # Intervent data:
        'intervention_report',
        'intervention_report_analysis',
        ],
    'init_xml': [],
    'demo': [],
    'data': [
        'security/security_group.xml',
        'security/ir.model.access.csv',

        'wizard/customer_activity_view.xml',
        'product_view.xml',
        'activity_storage_view.xml',
        'menu_view.xml',
        ],
    'active': False,
    'installable': True,
    'auto_install': False,
    }

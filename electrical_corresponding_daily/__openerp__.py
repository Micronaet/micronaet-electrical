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
    'name': 'Corresponding Management',
    'version': '0.1',
    'category': 'Account',
    'description': '''  
        Corresponding management:
        Create single receipt document and daily unload document with all line
        as detail.      
        ''',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'stock',
        'account',
        'metel_base', # Metel management
        'fast_stock_move', # Management of fast picking
        ],
    'init_xml': [],
    'demo': [],
    'data': [
        'security/ir.model.access.csv',
        'security/corresponding_group.xml',
        'data/receipt_sequence.xml',

        'report/corresponding_report.xml',
        
        'wizard/receipt_view.xml',
        'corresponding_view.xml',
        ],
    'active': False,
    'installable': True,
    'auto_install': False,
    }

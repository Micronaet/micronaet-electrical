#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
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
    'name' : 'Italian localization - Mx Invoice report aeroo',
    'version' : '0.1',
    'category' : 'Localization/Italy/Reporting',
    'description' : '''
        Base invoice in Aeroo:
        ''',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends' : [
        'base',
        'account',
        'report_aeroo',
        #'force_description', # TODO 
        #'report_aeroo_ooo',
        ],
    'init_xml' : [], 
    'data' : [
        'invoice_view.xml',
        'report/invoice_report.xml',
        ],
    'demo_xml' : [],
    'test': [],
    'active' : False, 
    'installable' : True, 
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

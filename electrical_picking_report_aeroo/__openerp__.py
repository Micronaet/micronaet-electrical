#!/usr/bin/python
# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2010-2012 Associazione OpenERP Italia
#    (<http://www.openerp-italia.org>).
#    Copyright(c)2008-2010 SIA "KN dati".(http://kndati.lv) All Rights Reserved.
#                    General contacts <info@kndati.lv>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name' : 'Electrical Picking Out aeroo report',
    'version' : '0.1',
    'category' : 'Localization/Italy/Reporting',
    'description' : """
        Picking report in aeroo according with extra field created in italian 
        localization
        """,
    'author': 'OpenERP Italian Community',
    'website': 'http://www.openerp-italia.org',
    'license': 'AGPL-3',
    'depends' : [
        'base',
        'report_aeroo',
        ],
    'init_xml' : [], 
    'data' : [
        'report/picking_report.xml',
        ],
    'demo_xml' : [],
    'test': [],
    'active' : False, 
    'installable' : True, 
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
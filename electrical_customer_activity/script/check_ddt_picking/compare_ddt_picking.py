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
import os
import pdb

import erppeek
import ConfigParser
import codecs

account_code = '1908'

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
cfg_file = os.path.expanduser('../openerp.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (
        server, port),
    db=dbname,
    user=user,
    password=pwd,
    )

pdb.set_trace()

# -----------------------------------------------------------------------------
# Extract package:
# -----------------------------------------------------------------------------
report_ids = []
ddt_pool = odoo.model('stock.ddt')
ddt_ids = ddt_pool.search([
    ('account_id.code', '=', account_code),
    ])
for ddt in ddt_pool.browse(ddt_ids):
    for picking in ddt.picking_ids:
        for move in picking.move_lines:
            report_ids.append(move.id)

stat_ids = []
picking_pool = odoo.model('stock.picking')
picking_ids = picking_pool.search([
    ('account_id.code', '=', account_code),  # This account code
    ('pick_move', '=', 'out'),  # Only out movement
    ('ddt_id', '!=', False),  # Linked in DDT
    ('ddt_id.is_invoiced', '=', False),  # Not invoiced
])
for picking in picking_pool.browse(picking_ids):
    for move in picking.move_lines:
        stat_ids.append(move.id)

# Set operations:
pdb.set_trace()
report_set = set(report_ids)
stat_set = set(stat_ids)

print('Report %s - Stat %s' % (len(report_set), len(stat_set)))
print(report_set.symmetric_difference(stat_set))
print(stat_set.symmetric_difference(report_set))


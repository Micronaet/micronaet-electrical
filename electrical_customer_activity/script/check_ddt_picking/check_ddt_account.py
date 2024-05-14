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

# -----------------------------------------------------------------------------
# Extract package:
# -----------------------------------------------------------------------------
pick_pool = odoo.model('stock.picking')
pick_ids = pick_pool.search([
    ('ddt_id', '!=', False),
    ])
pdb.set_trace()
csv_f = codecs.open('./ddt_account.csv', 'w', 'utf-8')

csv_f.write('DDT|Commessa|Picking|Commessa\n')
total = len(pick_ids)
counter = 0
for picking in pick_pool.browse(pick_ids):
    counter += 1
    if not (counter % 10):
        print('Read %s of %s' % (
            counter, total
        ))

    # DDT:
    ddt = picking.ddt_id
    ddt_name = ddt.name
    if ddt.account_id:
        account_code = ddt.account_id.code
    else:
        account_code = 'non trovato'

    if picking.account_id:
        picking_account = picking.account_id.code
    else:
        picking_account = 'non trovato'

    if picking_account != account_code:
        csv_f.write('%s|%s|%s|%s\n' % (
            ddt_name,
            account_code,
            picking.name,
            picking_account,
        ))
        csv_f.flush()

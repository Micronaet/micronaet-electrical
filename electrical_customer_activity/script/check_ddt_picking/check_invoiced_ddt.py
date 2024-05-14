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
ddt_pool = odoo.model('stock.ddt')
ddt_ids = ddt_pool.search([])
pdb.set_trace()
csv_f = codecs.open('./4.ddt_invoiced.csv', 'w', 'utf-8')

csv_f.write(
    'DDT|N Fattura|Data|Importo|(Fattura)|(Importo)|(Fatturato)|Stato\n')
total = len(ddt_ids)
counter = 0
for ddt in ddt_pool.browse(ddt_ids):
    counter += 1
    if not (counter % 10):
        print('Read %s of %s' % (
            counter, total
        ))

    manual_date = manual_amount = manual_number = ''
    invoice_number = ddt.invoice_number or ''
    invoice_amount = ddt.invoice_amount or ''
    is_invoiced = ddt.is_invoiced or ''

    if ddt.manual_invoice_id:
        invoice = ddt.manual_invoice_id
        manual_number = invoice.name
        manual_date = invoice.date
        # manual_account = invoice.account_id
        manual_amount = invoice.total
        state = 'CREATA'
    elif invoice_number:
        state = 'DA CREARE'
    else:
        state = 'DA FATTURARE'

    csv_f.write('%s|%s|%s|%s|%s|%s|%s|%s\n' % (
        ddt.name,

        manual_number,
        manual_date,
        manual_amount,

        invoice_number,
        invoice_amount,
        is_invoiced,
        state,
    ))
    csv_f.flush()

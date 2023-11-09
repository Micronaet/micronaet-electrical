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
product_pool = odoo.model('product.product')
ddt_pool = odoo.model('stock.ddt')
ddt_ids = ddt_pool.search([
    ('account_id.code', '=', account_code),
    ])
pdb.set_trace()
total = {
    'cost': 0.0,
    'discount': 0.0,
    'revenue': 0.0,
}
for ddt in ddt_pool.browse(ddt_ids):
    for picking in ddt.picking_ids:
        picking_account = picking.account_id.code
        if picking_account != account_code:
            print('[ERROR] Picking %s Account %s' % (
                picking.name,
                picking_account,
            ))
        else:
            print('[INFO] Picking %s Account %s' % (
                picking.name,
                picking_account,
            ))
        for move in picking.move_lines:
            product = move.product_id
            (product_name, list_price, standard_price,
             discount_price, discount_vat) = \
                product_pool.extract_product_data_erppeek(move.id)

            subtotal1 = \
                standard_price * move.product_qty
            subtotal2 = \
                discount_price * move.product_qty
            subtotal3 = \
                list_price * move.product_qty

            print('%s|%s|%s|%s|%s|%s|%s|%s\n' % (
                ddt.account_id.name,
                (ddt.delivery_date or ddt.date)[:10],
                product.default_code,
                product_name,
                move.product_uom.name,
                standard_price,
                discount_price,
                list_price,
                ))

            # A. Total per account:
            total['cost'] += subtotal1
            total['discount'] += subtotal2
            total['revenue'] += subtotal3

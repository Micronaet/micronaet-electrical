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
import erppeek
import ConfigParser

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
product_pool = odoo.model('product.product')
category_pool = odoo.model('product.category')

product_ids = product_pool.search([
    #('metel_statistic', '!=', False),
    #('metel_statistic_id', '=', False),
    ('metel_discount', 'not in', ('', False)),
    ('metel_discount_id', '=', False),
    ])

print 'Found %s product' % len(product_ids)
i = 0
created_group = []
discount_group = {}
import pdb; pdb.set_trace()
for product in product_pool.browse(product_ids):
    i += 1
    producer_code = product.metel_producer_code
    brand_code = product.metel_brand_code
    #metel_statistic = product.metel_statistic
    metel_discount = product.metel_discount
    
    # -------------------------------------------------------------------------
    # PARENT: Create producer > brand groups:
    # -------------------------------------------------------------------------
    if (producer_code, brand_code) in created_group: 
        metel_brand_id = created_group[
            (producer_code, brand_code)]
    else:
        metel_brand_id = category_pool.get_create_brand_group(
            producer_code, brand_code, brand_code)
    
    # -------------------------------------------------------------------------
    # Crete or get discount category:            
    # -------------------------------------------------------------------------
    try:
        key = (brand_code, metel_discount) # XXX no producer
    except:
        import pdb; pdb.set_trace()
    if key not in discount_group:
        category_ids = category_pool.search([
            ('parent_id', '=', metel_brand_id),
            ('metel_discount', '=', metel_discount),
            ('metel_mode', '=', 'discount'),
            ])
            
        if category_ids:
            discount_group[key] = category_ids[0]
        else:
            discount_group[key] = category_pool.create({
                'parent_id': metel_brand_id,
                'metel_discount': metel_discount,
                'name': metel_discount,
                'metel_mode': 'discount',
                }).id
                                
    product_pool.write(product.id, {
        'metel_discount_id': discount_group[key],
        })
    print '%s Update: [%s] %s' % (i, product.default_code, metel_discount)


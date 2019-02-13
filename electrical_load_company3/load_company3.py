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

import os
import sys
import logging
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class StockPickingFile(orm.Model):
    """ Model name: Stock picking input file
    """
    
    _inherit = 'stock.picking.input.file'
    
    def extract_data_from_supplier_file(self, cr, uid, partner, filename, 
            context=None):
        ''' Override procedure to extract data from file
        '''
        # -------------------------------------------------------------------------
        # Utility:    
        # -------------------------------------------------------------------------
        def _clean_string(value):
            ''' Clean extra space
            '''
            value = value or ''        
            return value.strip()

        def _clean_float(value, scale=1.0):
            ''' Clean extra space, return float / scale value
            '''
            value = value or ''
            value = value.strip().replace(',', '.')
            if not scale:
                return 0.0
            return float(value) / scale
        
        def _clean_date(value):
            ''' Return ODOO date format from ISO
            '''
            value = value or ''
            return '%s-%s-%s' % (
                value[:4],
                value[4:6],
                value[6:8],
                )

        code = partner.load_file_id.code
        if code != 'company3':
            # Go in parent overrided procedure: 
            return super(
                StockPickingFile, self).extract_data_from_supplier_file(
                    cr, uid, ids, partner, filename, context=context)

        # ---------------------------------------------------------------------
        # Company 1 Procedure:
        # ---------------------------------------------------------------------
        product_pool = self.pool.get('product.product')

        separator = ';'
        origin = ''
        rows = []

        i = 0
        for line in open(filename, 'r'):
            i += 1
            if i == 1:
                continue # jump header

            if not line.strip():
                _logger.error('Empty line, not considered')
                continue
            row = line.split(separator)

            # -------------------------------------------------------------
            # Extract parameter from line:
            # -------------------------------------------------------------
            company_ref = row[1] # DDT number
            sequence = 1 # Seq.
            order_ref = row[10] # Order ref
            default_code = '%s%s' % ( # 2 part
                _clean_string(row[13]),
                _clean_string(row[14]),
                )
            name = _clean_string(row[15])
            uom =  _clean_string(row[16])
            product_qty = _clean_float(row[17])
            price = _clean_float(row[18]) # Net

            # Search product:
            product_ids = product_pool.search(cr, uid, [
                ('default_code', '=', default_code),
                ], context=context)
            product_id = product_ids[0] if product_ids else False

            rows.append({
                'sequence': sequence,
                'name': name,
                'uom': uom,
                'original_code': default_code,
                'create_code': default_code,
                'product_id': product_id,
                'original_id': product_id,
                #'order_id': current_proxy.id,
                #'create_new': False,
                'product_qty': product_qty,
                'standard_price': price,
                })
                
            if not origin: # update only first time:
                # Parameter:
                origin = 'DDT: %s [%s]' % (
                    company_ref,
                    order_ref,
                    ) 

        return origin, rows # Unsorted

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

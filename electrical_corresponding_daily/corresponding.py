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

class StockPicking(orm.Model):
    """ Model name: StockPicking
    """
    
    _inherit = 'stock.picking'

    def dummy_button(self, cr, uid, ids, context=None):
        ''' Dummy button
        '''
        return True
    
    def correspond_checked_yes(self, cr, uid, ids, context=None):
        ''' Set to yes
        '''
        return self.write(cr, uid, ids, {
            'correspond_checked': True,
            }, context=context)

    def correspond_checked_no(self, cr, uid, ids, context=None):
        ''' Set to no
        '''
        return self.write(cr, uid, ids, {
            'correspond_checked': False,
            }, context=context)
            
    
    def _get_corresponding_total(self, cr, uid, ids, fields, args, 
            context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        vat = 1.22

        for picking in self.browse(cr, uid, ids, context=context):
            res[picking.id] = {
                'corresponding_total': 0.0,
                'corresponding_total_vat': 0.0,
                'corresponding_error': False,
                }
            if not picking.corresponding:
                continue
            for move in picking.move_lines:
                subtotal = move.price_unit * move.product_uom_qty
                if not subtotal:
                    res[picking.id]['corresponding_error'] = True
                res[picking.id]['corresponding_total'] += subtotal    
            res[picking.id]['corresponding_total_vat'] = \
                res[picking.id]['corresponding_total'] * vat
        return res

    _columns = {
        'corresponding_total': fields.function(
            _get_corresponding_total, method=True, 
            type='float', string='Corresponding', multi=True),
        'corresponding_total_vat': fields.function(
            _get_corresponding_total, method=True, 
            type='float', string='Corresponding VAT', multi=True),
        'corresponding_error': fields.function(
            _get_corresponding_total, method=True, 
            type='boolean', string='Corresponding', multi=True),
        'correspond_checked': fields.boolean('Corrispettivo terminato'),        
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

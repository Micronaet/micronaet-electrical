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
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class NewReceiptWizard(orm.TransientModel):
    ''' Wizard for New Receipt Wizard
    '''
    _name = 'new.receipt.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def dummy_action(self, cr, uid, ids, context=None):
        ''' Refresh button
        '''
        return True
        
    def action_done(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        
        
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        
        return {
            'type': 'ir.actions.act_window_close'
            }

    def _get_total(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for receipt in self.browse(cr, uid, ids, context=context)[0]:
            for line in receipt.line_ids:
                res[receipt.id] += line.qty * line.price
        return res
        
    _columns = {
        'name': fields.char('# Receipt', size=25, required=True),
        'total': fields.function(_get_total, method=True, 
            type='float', string='Total'),                        
        }

    _defaults = {
        # TODO name
        }

class NewReceiptLineWizard(orm.TransientModel):
    ''' Wizard for New Receipt Wizard
    '''
    _name = 'new.receipt.line.wizard'

    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        ''' Change default price from product form
        '''
        res = {'value': {'price': 0.0}}
        if not product_id:
            return res
            
        product_pool = self.pool.get('product.product')    
        product_proxy = product_pool.browse(
            cr, uid, product_id, context=context)
        # TODO change price?
        res['value']['price'] = product_proxy.standard_price
        return res

    _columns = {
        'wizard_id': fields.many2one('new.receipt.wizard', 'Wizard'),
        'product_id': fields.many2one('product.product', 'Product'),
        'uom_id': fields.related(
            'product_id', 'uom_id', 
            type='many2one', relation='product.uom', 
            string='UOM', readonly=True),
        'qty': fields.float('Q.', digits=(16, 2), required=True),
        'price': fields.float('Price', digits=(16, 4), required=True),
        }

class NewReceiptWizard(orm.TransientModel):
    ''' Wizard for New Receipt Wizard
    '''
    _inherit = 'new.receipt.wizard'
    
    _columns = {
        'line_ids': fields.one2many(
            'new.receipt.line.wizard', 'wizard_id', 'Detail'),
        }
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

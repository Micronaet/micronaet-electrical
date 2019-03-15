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

    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------
    def dummy_action(self, cr, uid, ids, context=None):
        ''' Refresh button
        '''
        return True

    def action_done(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}
        
        name = self.pool.get('ir.sequence').get(cr, uid, 'new.receipt.wizard')
        self.write(cr, uid, ids, {
            'name': name,
            }, context=context)
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]

        # ---------------------------------------------------------------------
        # Create new corresponding:
        # ---------------------------------------------------------------------
        # Pool used:
        company_pool = self.pool.get('res.company')
        picking_pool = self.pool.get('stock.picking')
        move_pool = self.pool.get('stock.move')        
        quant_pool = self.pool.get('stock.quant')                
        type_pool = self.pool.get('stock.picking.type')

        now = ('%s' % datetime.now())[:19]
        origin = 'CORRISPETTIVO %s' % now[:10]

        # ---------------------------------------------------------------------
        # Search or create daily picking:
        # ---------------------------------------------------------------------
        picking_ids = picking_pool.search(cr, uid, [
            ('corresponding', '=', True),
            ('origin', '=', origin),
            ], context=context)        
        if picking_ids:
            picking_id = picking_ids[0]
            picking = picking_pool.browse(
                cr, uid, picking_ids, context=context)[0]
            # Parameters:    
            picking_type = picking.picking_type_id
            location_id = picking_type.default_location_src_id.id
            location_dest_id = picking_type.default_location_dest_id.id                
            company_id = picking.company_id.id
        else:        
            company_id = company_pool.search(cr, uid, [], context=context)[0]
            company = company_pool.browse(cr, uid, company_id, context=context)

            # Type ID:
            type_ids = type_pool.search(cr, uid, [
                ('code', '=', 'outgoing'),
                ], context=context)
            if not type_ids:
                raise osv.except_osv(
                    _('Error'), 
                    _('Need setup of outgoing stock.picking.type!'),
                    )    
            picking_type = \
                type_pool.browse(cr, uid, type_ids, context=context)[0]
            location_id = picking_type.default_location_src_id.id
            location_dest_id = picking_type.default_location_dest_id.id
            
            picking_id = picking_pool.create(cr, uid, {
                'partner_id': company.partner_id.id,
                'company_id': company_id,
                'corresponding': True,
                #'account_id': account.id,
                'date': now,
                'min_date': now,
                'origin': origin,
                'picking_type_id': picking_type.id,
                'pick_move': 'out',
                'pick_state': 'delivered',
                #'state': 'delivered', # XXX not real!
                }, context=context)

        # ---------------------------------------------------------------------
        # Add stock movement line:
        # ---------------------------------------------------------------------
        receipt = wiz_proxy.name
        for line in wiz_proxy.line_ids:
            product = line.product_id
            price = line.price
            qty = line.qty
            
            # -----------------------------------------------------------------
            # Create stock movement:
            # -----------------------------------------------------------------
            move_id = move_pool.create(cr, uid, {
                'name': product.name,
                'product_uom': product.uom_id.id,
                'picking_id': picking_id,
                'picking_type_id': picking_type.id,
                'origin': 'Scontr: %s' % receipt,
                'product_id': product.id,
                'product_uom_qty': qty,
                'date': now,
                'location_id': location_id,
                'location_dest_id': location_dest_id,
                'state': 'done',
                'price_unit': price,
                }, context=context)

            # -----------------------------------------------------------------
            # Create quants:
            # -----------------------------------------------------------------
            quant_pool.create(cr, uid, {
                 'stock_move_id': move_id,
                 'qty': qty,
                 'cost': price,
                 'location_id': location_dest_id,
                 'company_id': company_id,
                 'product_id': product.id,
                 'in_date': now,
                }, context=context)
        
        return self.write(cr, uid, ids, {
            'state': 'done',
            }, context=context)

    def _get_total(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        vat = 1.22
        res = {}
        for receipt in self.browse(cr, uid, ids, context=context)[0]:
            res[receipt.id] = {'total': 0.0}
            for line in receipt.line_ids:
                subtotal = line.qty * line.price
                res[receipt.id]['total'] += subtotal
            res[receipt.id]['total_vat'] = res[receipt.id]['total'] * vat
        return res
        
    _columns = {
        'name': fields.char('# Receipt', size=25),
        'total': fields.function(_get_total, method=True, 
            type='float', string='Total', multi=True),      
        'total_vat': fields.function(_get_total, method=True, 
            type='float', string='Total VAT', multi=True),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('done', 'Done'),
            ], 'State', readonly=True),
        }

    _defaults = {
        # Default value for state:
        'state': lambda *x: 'draft',
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
        #res['value']['price'] = product_proxy.standard_price
        res['value']['price'] = product_proxy.lst_price
        return res

    def _get_subtotal_value(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        vat_rate = 1.22 # TODO keep in parameter field!
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            price_vat = line.price * vat_rate
            res[line.id] = {
                'price_vat': price_vat,
                'subtotal': price_vat * line.qty,
                }
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
        'price_vat': fields.function(
            _get_subtotal_value, method=True, type='float', string='Price VAT',
            readonly=True, multi=True),                         
        'subtotal': fields.function(
            _get_subtotal_value, method=True, type='float', string='Subtotal',
            readonly=True, multi=True),
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

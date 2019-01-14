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

class StockMove(orm.Model):
    """ Model name: PurchaseOrder
    """
    
    _inherit = 'stock.move'
    
    _columns = {
        'electrical_line_id': fields.many2one(
            'purchase.order.line', 'Purchase line'),
        }

class PurchaseOrder(orm.Model):
    """ Model name: PurchaseOrder
    """
    
    _inherit = 'purchase.order'

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    def unlink_electrical_stock_move(self, cr, uid, ids, context=None):
        ''' Unlink stock movement when confirmed 
        '''
        _logger.info('Remove stock move linked to purchase line')

        move_pool = self.pool.get('stock.move')
        line_ids = [line.id for line in \
            self.browse(cr, uid, ids, context=context)[0].order_line]
        if not line_ids:
            return True    

        move_ids = move_pool.search(cr, uid, [
            ('electrical_line_id', 'in', line_ids),
            ], context=context)
        if not move_ids:
            return True
        
        # Put in draft to delete:
        move_pool.write(cr, uid, move_ids, {
            'state': 'draft',
            }, context=context)  
        # Delete:      
        return move_pool.unlink(cr, uid, move_ids, context=context)
        
    def create_electrical_stock_move(self, cr, uid, ids, context=None):
        ''' Create stock movement when confirmed 
        '''
        move_pool = self.pool.get('stock.move')
        type_pool = self.pool.get('stock.picking.type')

        # ---------------------------------------------------------------------
        # Parameters:
        # ---------------------------------------------------------------------
        now = ('%s' % datetime.now())[:19]

        # Type ID:
        type_ids = type_pool.search(cr, uid, [
            ('code', '=', 'incoming'),
            ], context=context)
        if not type_ids:
            raise osv.except_osv(
                _('Error'), 
                _('Need setup of outgoing stock.picking.type!'),
                ) 
        picking_type = type_pool.browse(cr, uid, type_ids, context=context)[0]           
        location_id = picking_type.default_location_src_id.id
        location_dest_id = picking_type.default_location_dest_id.id
        
        # Unlink previous line:
        _logger.info('Create stock move linked to purchase line')
        self.unlink_electrical_stock_move(cr, uid, ids, context=context)
        
        # Create new line:
        purchase = False
        for line in self.browse(cr, uid, ids, context=context)[0].order_line:
            if not purchase:
                purchase = line.order_id
            product = line.product_id
            move_pool.create(cr, uid, {
                'electrical_line_id': line.id,

                'name': product.name,
                'product_uom': product.uom_id.id,
                'picking_id': False,
                'picking_type_id': picking_type.id,
                'origin': '%s [%s]' % (
                    purchase.name, (purchase.date_order, '')[:10]),
                'product_id': product.id,
                'product_uom_qty': line.product_qty,
                'date': now,
                'location_id': location_id,
                'location_dest_id': location_dest_id,
                'state': 'assigned',                
                }, context=context)
        
    # -------------------------------------------------------------------------
    # Workflow button:    
    # -------------------------------------------------------------------------
    def wkf_electrical_set_draft(self, cr, uid, ids, context=None):
        ''' Secondary WF Button:
        '''        
        return self.write(cr, uid, ids, {
            'electrical_state': 'draft',
            }, context=context)

    def wkf_electrical_set_sent(self, cr, uid, ids, context=None):
        ''' Secondary WF Button:
        '''
        # Create movement to update stock status:
        self.create_electrical_stock_move(cr, uid, ids, context=context)
        
        return self.write(cr, uid, ids, {
            'electrical_state': 'sent',
            }, context=context)

    def wkf_electrical_set_done(self, cr, uid, ids, context=None):
        ''' Secondary WF Button:
        '''
        # Remove stock movement so update stock status:
        self.unlink_electrical_stock_move(cr, uid, ids, context=context)

        return self.write(cr, uid, ids, {
            'electrical_state': 'done',
            }, context=context)
    
    _columns = {
        'electrical_state': fields.selection([
            ('draft', 'Draft'),
            ('sent', 'Sent'),
            ('done', 'Done'),
            ], 'Purchase state'),
        }
    
    _defaults = {
        'electrical_state': lambda *x: 'draft',
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

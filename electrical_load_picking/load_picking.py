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
    
    _name = 'stock.picking.input.file'
    _description = 'Picking in file'
    _rec_name = 'name'
    _order = 'name'

    # -------------------------------------------------------------------------
    # Utility:    
    # -------------------------------------------------------------------------
    def _clean_string(self, value):
        ''' Clean extra space
        '''
        value = value or ''        
        return value.strip()

    def _clean_mode(self, value):
        ''' Clean mode
        '''
        value = value or ''        
        if value.upper() == 'D': # DDT
            return 'in'
        else: 
            return 'out'
        
    def _clean_float(self, value, scale=1.0):
        ''' Clean extra space, return float / scale value
        '''
        value = value or ''
        if not scale:
            return 0.0
        return float(value) / scale
    
    def _clean_date(self, value):
        ''' Return ODOO date format from ISO
        '''
        value = value or ''
        return '%s-%s-%s' % (
            value[:4],
            value[4:6],
            value[6:8],
            )
    
    def load_document(self, cr, uid, ids, context=None):
        ''' Load document of new file 
        '''
        if context is None:
            context = {}
        state = context.get('import_state', 'load') # else close
        
        # Pool used:
        picking_pool = self.pool.get('stock.picking')
        move_pool = self.pool.get('stock.mode')
        
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # ---------------------------------------------------------------------
        # Clean situation:
        # ---------------------------------------------------------------------
        if state != 'load' and current_proxy.picking_id:
            # TODO remove quants:
            
            # TODO remove movements:
            
            # -----------------------------------------------------------------
            # Delete picking
            # -----------------------------------------------------------------
            picking_pool.unlink(cr, uid, [ # TODO keep it?
                current_proxy.picking_id.id], context=context)

        partner = current_proxy.partner_id
        filename = os.path.join(
            partner.electrical_path, 
            current_proxy.name,
            )

        picking_id = False    
        content = ''
        for line in open(filename, 'r'):
            # -----------------------------------------------------------------
            # Extract parameter from line:
            # -----------------------------------------------------------------
            address_code = self._clean_string(line[:3])
            mode = line[3:5] # TODO mode filter
            year = self._clean_string(line[5:9])
            supplier_code = self._clean_string(line[9:16])
            supplier_date = self._clean_date(line[16:24]) # ISO format
            sequence = self._clean_string(line[24:29])
            protocol = self._clean_string(line[29:38])
            default_code = self._clean_string(line[38:58])
            name = self._clean_string(line[58:118])
            uom = self._clean_string(line[118:120])
            product_qty = self._clean_float(line[120:131], 1000.0)
            price = self._clean_string(line[131:144], 100000.0)
            company_ref = self._clean_string(line[144:159])
            company_date = self._clean_date(line[160:168]) # XXX jump one char
            company_number = self._clean_string(line[168:175])

            content += 'Art.: %s Q. %s %s x %s EUR\n' % (
                default_code,
                product_qty,
                uom,
                price,
                )

            if state != 'load':
                continue # not create picking + movement
                    
            # -----------------------------------------------------------------
            # Create new pick:
            # -----------------------------------------------------------------
            if not picking_id:
                picking_id =  picking_pool.create(cr, uid, {
                    'partner_id': partner.id,
                    # TODO
                    }, context=context)
            
            # -----------------------------------------------------------------
            # Create stock move:
            # -----------------------------------------------------------------
            move_pool.create(cr, uid, {
                'picking_id': picking_id,
                # TODO 
                }, context=context)
        
        # Update document file:        
        self.write(cr, uid, current_proxy.id, {
            'state': state,
            'content': content,
            }, context=context)
        return True

    _columns = {
        'create_date': fields.date('Create date'),
        'name': fields.char(
            'Name', size=80, required=True),
        'picking_id': fields.many2one('stock.picking', 'Picking'),
        'partner_id': fields.many2one('res.partner', 'Partner', required=True),
        'address_id': fields.many2one('res.partner', 'Address'),
        'content': fields.text('Content'),
        'mode': fields.selection([
            ('in', 'In document'), # Delivery
            ('out', 'Out document'), # Wrong delivery
            ], 'Flow mode'),
        'state': fields.selection([
            ('draft', 'Draft'), # Start phase
            ('load', 'Loaded'), #  With document
            ('close', 'Closed'), # Without document
            ], 'State'),
        }
    
    _defaults = {
        # Default value:
        'state': lambda *x: 'draft',
        }

class ResPartnerFolder(orm.Model):
    """ Model name: ResPartnerFolder
    """    
    _inherit = 'res.partner'
    
    # -------------------------------------------------------------------------
    # Button events:
    # -------------------------------------------------------------------------
    # A) Load files into record:
    def electrical_load_picking_routine(self, cr, uid, ids, context=None):
        ''' Start procedure for load documents from folder
        '''
        file_pool = self.pool.get('stock.picking.input.file')
        
        file_ids = file_pool.search(cr, uid, [
            ('partner_id', '=', ids[0]),
            ], context=context)
        current_list = [item.name for item in file_pool.browse(
            cr, uid, file_ids, context=context)]
        
        # Read files from partner folder:    
        partner_proxy = self.browse(cr, uid, ids, context=context)[0]    
        path = os.path.expanduser(partner_proxy.electrical_path)
        extension = (partner_proxy.electrical_extension or '').lower()
        
        ctx = context.copy()
        ctx['import_state'] = 'draft'
        file_ids = []
        for root, folder, files in os.path:
            for f in files:
                if f.split('.')[-1].lower() != extension:
                    _logger.warning('Wrong estension [%s]: %s' % (
                        estension, f))
                    continue # jump not same extension
                if f in current_list:
                    _logger.warning('Yet loaded: %s' % f)
                    continue # jump not same extension
                
                # Create record:
                file_id = file_pool.create(cr, uid, {}, context=ctx)
                file_ids.append(file_id)
                # Load document (draft mode)
                file_pool.load_document(cr, uid, [file_id], context=ctx)
            break

        return {
            'type': 'ir.actions.act_window',
            'name': _('File loaded'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': 1,
            'res_model': 'stock.picking.input.file',
            #'view_id': view_id, # False
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [('id', 'in', file_ids)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

        
    # B) Generate picking from file loaded:
    def electrical_generate_picking_routine(self, cr, uid, ids, context=None):
        ''' Start procedure for load documents from folder
        '''
        file_pool = self.pool.get('stock.picking.input.file')
        
        file_ids = file_pool.search(cr, uid, [
            ('state', '=', 'draft'),
            ('partner_id', '=', ids[0]),
            ], context=context)

        file_pool.write(cr, uid, file_ids, {
            'state': 'load', 
            }, context=context)
        return {
            'type': 'ir.actions.act_window',
            'name': _('File loaded'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': 1,
            'res_model': 'stock.picking.input.file',
            #'view_id': view_id, # False
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [('id', 'in', file_ids)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    # A + B) Load and generate all:    
    def electrical_all_picking_routine(self, cr, uid, ids, context=None):
        ''' Start procedure for load documents from folder
        '''
        self.electrical_load_picking_routine(cr, uid, ids, context=context)
        self.electrical_generate_picking_routine(cr, uid, ids, context=context)
        return True

    def open_electrical_file_ids(self, cr, uid, ids, context=context):
        ''' 
        '''
        file_pool = self.pool.get('stock.picking.input.file')
        file_ids = file_pool.search(cr, uid, [
            ('partner_id', '=', ids[0]),
            ], context=context)
            
        #model_pool = self.pool.get('ir.model.data')
        #view_id = model_pool.get_object_reference('module_name', 'view_name')[1]
        return {
            'type': 'ir.actions.act_window',
            'name': _('File loaded'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': 1,
            'res_model': 'stock.picking.input.file',
            #'view_id': view_id, # False
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [('id', 'in', file_ids)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }
            
    _columns = {       
        'electrical_path': fields.char(
            'Picking folder', size=180, 
            help='Load document folder'),
        'electrical_estension': fields.char(
            'File estension', size=6, 
            help='Document file estension'),
        'electrical_address_code': fields.char(
            'Address code', size=10, 
            help='Address code used for input destination search'),
        'electric_file_ids': fields.one2many(
            'stock.picking.input.file', 'partner_id', 'Electric document'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

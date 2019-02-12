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
from openerp import SUPERUSER_ID
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
            
    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    def onchange_customer_id(
            self, cr, uid, ids, customer_id, context=None):
        ''' Change domain depend on partner
        '''    
        domain = [
            ('type', 'in', ('normal', 'contract')),
            ('state', '!=', 'close'),
            ('use_timesheets', '=', 1),            
            ]
        if customer_id:
            domain.append(('partner_id', '=', customer_id)) # Customer account
        else:    
            domain.append(('partner_id', '!=', False)) # All account

        return {'domain': {
            'account_id': domain,
            }}
    # -------------------------------------------------------------------------
    # Button document:
    # -------------------------------------------------------------------------
    def generate_pick_out_draft(self, cr, uid, ids, context=None):
        ''' Create pick out document depend on account analytic
        '''
        #`Pool used:
        picking_pool = self.pool.get('stock.picking')
        file_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        picking_id = file_proxy.picking_id.id
        if not picking_id:
            raise osv.except_osv(
                _('Error'), 
                _('No pick generated from this file!'),
                )    

        self.write(cr, uid, ids, {
            'state': 'close',
            }, context=context)

        return picking_pool.generate_pick_out_draft(
            cr, uid, [picking_id], context=context)
        
    def load_document(self, cr, uid, ids, context=None):
        ''' Load document of new file 
        '''
        if context is None:
            context = {}

        # Pool used:
        company_pool = self.pool.get('res.company')
        product_pool = self.pool.get('product.product')
        uom_pool = self.pool.get('product.uom')
        picking_pool = self.pool.get('stock.picking')
        type_pool = self.pool.get('stock.picking.type')
        move_pool = self.pool.get('stock.move')
        quant_pool = self.pool.get('stock.quant')
        line_pool = self.pool.get('stock.picking.input.file.line')

        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # Parameter:
        company_id = company_pool.search(cr, uid, [], context=context)[0]
        state = context.get('import_state', 'load') # passed draft or load
        now = ('%s' % datetime.now())[:19]
        
        type_ids = type_pool.search(cr, uid, [
            ('code', '=', 'incoming'),
            ], context=context)
        if not type_ids:
            raise osv.except_osv(
                _('Error'), 
                _('Need setup of incoming stock.picking.type!'),
                )    
        picking_type = type_pool.browse(cr, uid, type_ids, context=context)[0]
        location_id = picking_type.default_location_src_id.id
        location_dest_id = picking_type.default_location_dest_id.id

        # ---------------------------------------------------------------------
        # Clean situation:
        # ---------------------------------------------------------------------
        picking_id = current_proxy.picking_id.id or False
        partner = current_proxy.partner_id

        # Remove picking if present:
        #if state == 'load' and picking_id:
        #    # Remove quants:
        #    context['force_unlink'] = True
        #    quant_ids = quant_pool.search(cr, uid, [
        #        ('stock_move_id.picking_id', '=', picking_id),
        #        ], context=context)
        #    quant_pool.unlink(cr, uid, quant_ids, context=context)    

        #    # Remove movements:
        #    move_ids = move_pool.search(cr, uid, [
        #        ('picking_id', '=', picking_id),
        #        ], context=context)
        #    move_pool.unlink(cr, uid, move_ids, context=context)                
        #    # XXX NO: Remove picking: 
        
        # ---------------------------------------------------------------------
        # Read file:
        # ---------------------------------------------------------------------
        if state == 'draft':        
            filename = os.path.join(
                os.path.expanduser(partner.electrical_path), 
                current_proxy.name,
                )
            _logger.warning('Reading file: %s' % filename)    

            line_ids = []
            error = False
            
            sorted_line = sorted(
                open(filename, 'r'), 
                key=lambda line: line[24:29], # sequence code
                )

            for line in sorted_line:
                if not line.strip():
                    _logger.error('Empty line, not considered')
                    continue
                    
                # -----------------------------------------------------------------
                # Extract parameter from line:
                # -----------------------------------------------------------------
                address_code = self._clean_string(line[:3]) # ID Company
                mode = self._clean_mode(line[3:5]) # Causal
                year = self._clean_string(line[5:9]) # Year
                supplier_code = self._clean_string(line[9:16]) # DDT
                supplier_date = self._clean_date(line[16:24]) # DDT date ISO
                sequence = self._clean_string(line[24:29]) # Seq.
                protocol = self._clean_string(line[29:38]) # 
                default_code = self._clean_string(line[38:58])
                name = self._clean_string(line[58:118])
                uom = self._clean_string(line[118:120])
                product_qty = self._clean_float(line[120:131], 1000.0)
                price = self._clean_float(line[131:144], 100000.0)
                company_ref = self._clean_string(line[144:159]) # Order
                company_date = self._clean_date(line[160:168])#XXX jump 1 char
                company_number = self._clean_string(line[168:175])

                product_ids = product_pool.search(cr, uid, [
                    ('default_code', '=', default_code),
                    ], context=context)
                product_id = product_ids[0] if product_ids else False
                
                # Error management:
                if not product_id:
                    error = True

                # Create line not linked (done after):
                line_id = line_pool.create(cr, uid, {
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
                    }, context=context)
                line_ids.append(line_id)

                # -------------------------------------------------------------
                # Create new empty pick:
                # -------------------------------------------------------------
                # Parameter:
                origin = 'DDT %s [%s] %s' % (
                    supplier_code,
                    supplier_date,
                    '',
                    #company_number,
                    #company_date,
                    #company_ref,
                    )

                # Data:
                data = {
                    'partner_id': partner.id,
                    'date': now,
                    'min_date': now,
                    'origin': origin,
                    
                    'picking_type_id': picking_type.id,

                    'pick_move': 'in', # XXX dept to add!
                    'pick_state': 'delivered',
                    #'state': 'delivered', # XXX not real!
                    }
                if picking_id:
                    picking_pool.write(
                        cr, uid, picking_id, data, context=context)
                else:
                    picking_id = picking_pool.create(
                        cr, uid, data, context=context)
            
            # -----------------------------------------------------------------
            # Update document file:
            # -----------------------------------------------------------------
            self.write(cr, uid, current_proxy.id, {
                'state': state,
                'line_ids': [(6, 0, line_ids)],
                'picking_id': picking_id,
                'error': error,
                }, context=context)

        # ---------------------------------------------------------------------
        # Load picking:
        # ---------------------------------------------------------------------
        else: # load mode
            picking = current_proxy.picking_id
            default_account = current_proxy.account_id.id or False
            for line in sorted(
                    current_proxy.line_ids, 
                    key=lambda x: x.sequence):
                product_id = line.product_id.id
                uom_id = line.product_id.uom_id.id or 1
                
                if line.create_new:
                    create_code = line.create_code
                    product_ids = product_pool.search(cr, uid, [
                        ('default_code', '=', create_code),
                        ], context=context)
                    if product_ids:
                        product_id = product_ids[0]
                    else:
                        uom_ids = uom_pool.search(cr, uid, [
                            '|',
                            ('metel_code', '=', line.uom),
                            ('name', '=', line.uom),
                            ], context=context)
                        uom_id = uom_ids[0] if uom_ids else 1
                        
                        # -----------------------------------------------------
                        # Insert also brand code for update with METEL import:
                        # -----------------------------------------------------
                        #brand_code = create_code[:3].upper()
                        #if '-' in brand_code:
                        #    brand_code = False # Internal code

                        product_id = product_pool.create(cr, uid, {
                            # METEL Brand (needed for sync with import proc.)
                            #'metel_brand_code': brand_code,
                            #'metel_producer_code': brand_code,

                            'name': line.name,
                            'default_code': create_code,
                            'standard_price': line.standard_price,
                            'uom_id': uom_id,
                            'uos_id': uom_id,
                            'uom_po_id': uom_id,
                            # TODO extra data?
                            }, context=context)    

                if not product_id:
                    raise osv.except_osv(
                        _('Error'), 
                        _('Error no product selected!'),
                        )

                # Parameters:
                product_qty = line.product_qty

                # TODO Use WK button in load procedure (fast_stock_move)?                
                # -------------------------------------------------------------
                # Create stock move:
                # -------------------------------------------------------------
                move_id = move_pool.create(cr, uid, {
                    'name': line.name,
                    'product_uom': uom_id,
                    'picking_id': picking.id,
                    'picking_type_id': picking_type.id,
                    'origin': picking.origin,
                    'product_id': product_id,
                    'product_uom_qty': product_qty,
                    'date': now,
                    'location_id': location_id,
                    'location_dest_id': location_dest_id,
                    'state': 'done',
                    'price_unit': line.standard_price,

                    # Auto pick out data:
                    'auto_account_out_id':
                        line.account_id.id or default_account
                    }, context=context)

                # -------------------------------------------------------------
                # Create stock quant:
                # -------------------------------------------------------------
                quant_pool.create(cr, uid, {
                     'stock_move_id': move_id, # Back link
                     
                     'qty': product_qty,
                     'cost': line.standard_price,
                     'location_id': location_dest_id,
                     'company_id': company_id,
                     'product_id': product_id,
                     'in_date': now,
                     #'propagated_from_id'
                     #'package_id'
                     #'lot_id'
                     #'reservation_id'
                     #'owner_id'
                     #'packaging_type_id'
                     #'negative_move_id'
                    }, context=context)
            
            # Update product product data:
            picking_pool.update_standard_price_product(
                cr, uid, [picking.id], context=context)
                
            # Correct error state (if present):
            self.write(cr, uid, ids, {
                'state': state,
                'error': False,
                }, context=context)        
        return True

    _columns = {
        'create_date': fields.date('Create date'),
        'error': fields.boolean('Error'),
        'name': fields.char(
            'Name', size=80, required=True),
        'picking_id': fields.many2one('stock.picking', 'Picking'),
        'partner_id': fields.many2one('res.partner', 'Partner', required=True),
        'address_id': fields.many2one('res.partner', 'Address'),

        # Analytic management:
        'customer_id': fields.many2one('res.partner', 'Customer'),
        'account_id': fields.many2one(
            'account.analytic.account', 'Analitic account'),

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

class StockPickingFileLine(orm.Model):
    """ Model name: Stock picking input file line
    """    
    _name = 'stock.picking.input.file.line'
    _description = 'Picking in file line'
    _rec_name = 'name'
    _order = 'sequence'

    _columns = {
        'sequence': fields.integer('Seq.'),
        'name': fields.char('Product name', size=64, required=True),
        'uom': fields.char('UOM', size=10),

        # Code:
        'original_code': fields.char('Original Code', size=64, required=True),
        'create_code': fields.char('Create code', size=64, required=True),

        # Product:
        'product_id': fields.many2one('product.product', 'Product'),
        'original_id': fields.many2one('product.product', 'Original'),

        'account_id': fields.many2one(
            'account.analytic.account', 'Analitic account'),

        'order_id': fields.many2one('stock.picking.input.file', 'File', 
            ondelete='cascade'),
        'create_new': fields.boolean('Create new product'),

        'product_qty': fields.float('Q.', digits=(16, 2), required=True),
        'standard_price': fields.float(
            'Unit price', digits=(16, 2), required=True),
        }

class StockPickingFile(orm.Model):
    """ Model name: Stock picking input file
    """
    
    _inherit = 'stock.picking.input.file'
    
    _columns = {
        'line_ids': fields.one2many(
            'stock.picking.input.file.line', 'order_id', 'Order'),
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
        if context is None:
            context = {}
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
        for root, folder, files in os.walk(path):
            for f in files:
                if f.split('.')[-1].lower() != extension:
                    _logger.warning('Wrong estension [%s]: %s' % (
                        extension, f))
                    continue # jump not same extension
                if f in current_list:
                    _logger.warning('Yet loaded: %s' % f)
                    continue # jump not same extension
                
                # Create record:
                file_id = file_pool.create(cr, uid, {
                    'partner_id': ids[0],
                    'name': f,
                    'state': 'draft',
                    'mode': 'in',
                    }, context=context)

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
        self.electrical_load_picking_routine(
            cr, uid, ids, context=context)
        return self.electrical_generate_picking_routine(
            cr, uid, ids, context=context)

    def open_electrical_file_ids(self, cr, uid, ids, context=None):
        ''' Open tree list of files
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
        'electrical_extension': fields.char(
            'File estension', size=6, 
            help='Document file estension'),
        'electrical_address_code': fields.char(
            'Address code', size=10, 
            help='Address code used for input destination search'),
        'electric_file_ids': fields.one2many(
            'stock.picking.input.file', 'partner_id', 'Electric document'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

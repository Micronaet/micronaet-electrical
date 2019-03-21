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


class ProductMetelGroupWizard(orm.TransientModel):
    ''' Wizard for manage product metel group
    '''
    _name = 'product.metel.group.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_update(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        
        
        category_pool = self.pool.get('product.category')

        wiz_browse = self.browse(cr, uid, ids, context=context)[0]        
        product = wiz_browse.product_id
        
        # ---------------------------------------------------------------------
        # Metel parent:
        # ---------------------------------------------------------------------
        category_ids = category_pool.search(cr, uid, [
            ('metel_mode', '=', 'metel'),
            ], context=context)
        if not category_ids:
            raise osv.except_osv(
                _('Error'), 
                _('No METEL parent category!'),
                )    
        metel_id = category_ids[0]
                
        product_data = {}
        
        # ---------------------------------------------------------------------
        # Producer:
        # ---------------------------------------------------------------------
        import pdb; pdb.set_trace()
        producer_code = wiz_browse.producer_code.upper()
        producer_category_id = product.producer_category_id.id
        if not producer_category_id:
            producer_ids = category_pool.search(cr, uid, [
                ('metel_mode', '=', 'producer'),
                ('metel_code', 'ilike', producer_code),
                ], context=context)
            if producer_ids:
                producer_category_id = producer_ids[0]    
        
        if producer_code and not producer_category_id:
            producer_category_id = category_pool.create(cr, uid, {
                'parent_id': metel_id,
                'name': producer_code,
                'metel_code': producer_code,
                'type': 'normal',
                'metel_mode': 'producer',
                }, context=context)

            product_data['metel_producer_id'] = producer_category_id
            product_data['metel_producer_code'] = producer_code

        # ---------------------------------------------------------------------
        # Brand:
        # ---------------------------------------------------------------------
        brand_code = wiz_browse.brand_code.upper()
        brand_category_id = product.brand_category_id.id
        if not brand_category_id:
            brand_ids = category_pool.search(cr, uid, [
                ('parent_id', '=', producer_category_id),
                ('metel_mode', '=', 'brand'),
                ('metel_code', 'ilike', brand_code),
                ], context=context)
            if brand_ids:
                brand_category_id = brand_ids[0]    
        
        if brand_code and not brand_category_id:
            brand_category_id = category_pool.create(cr, uid, {
                'parent_id': producer_category_id,
                'name': brand_code,
                'metel_code': brand_code,
                'type': 'normal',
                'metel_mode': 'brand',
                }, context=context)

            product_data['metel_brand_id'] = brand_category_id
            product_data['metel_brand_code'] = brand_code

        # ---------------------------------------------------------------------
        # Discount:
        # ---------------------------------------------------------------------
        discount_code = wiz_browse.discount_code.upper()
        if not discount_code:
            return True

        discount_category_id = product.metel_discount_id.id
        if not discount_category_id:
            discount_ids = category_pool.search(cr, uid, [
                ('parent_id', '=', brand_category_id),
                ('metel_mode', '=', 'discount'),
                ('metel_code', 'ilike', discount_code),
                ], context=context)
            if discount_ids:
                discount_category_id = discount_ids[0]    
        
        if discount_code and not discount_category_id:
            discount_id = category_pool.create(cr, uid, {
                'parent_id': brand_category_id,
                'name': discount_code,
                'metel_code': discount_code,
                'type': 'normal',
                'metel_mode': 'discount',
                }, context=context)

            product_data['metel_discount_id'] = discount_id
            product_data['metel_discount_code'] = discount_code

        return True

    # -------------------------------------------------------------------------
    # Utility function:
    # -------------------------------------------------------------------------
    def get_passed_product(self, cr, uid, context=None):
        product_id = context.get('default_product_id')
        
        product_pool = self.pool.get('product.product')
        return product_pool.browse(cr, uid, product_id, context=context)
        
    # -------------------------------------------------------------------------
    # Field function:
    # -------------------------------------------------------------------------
    def generate_default_code(self, cr, uid, context=None):
        ''' Generate default code[3]
        '''
        product = self.get_passed_product(cr, uid, context=context)
        return (product.default_code or '')[:3]        

    def generate_category_id(self, cr, uid, mode, context=None):
        ''' Generate producer if present
        '''
        product = self.get_passed_product(cr, uid, context=context)

        if mode == 'producer':
            return product.metel_producer_id.id
        elif mode == 'brand':
            return product.metel_brand_id.id
        else:    
        #elif mode == 'discount':
            return product.metel_discount_id.id

    _columns = {
        'product_id': fields.many2one(
            'product.product', 'Product', 
            help='Product selected in sale order line'),
        'producer_code': fields.char('Producer Code', size=3),            
        'brand_code': fields.char('Brand Code', size=3),
        'discount_code': fields.char('Discount Code', size=20),
        
        'producer_category_id': fields.many2one(
            'product.category', 'Producer category'),
        'brand_category_id': fields.many2one(
            'product.category', 'Brand category'),
        'discount_category_id': fields.many2one(
            'product.category', 'Discount category'),
        }
        
    _defaults = {
        'producer_code': lambda s, cr, uid, ctx: 
            s.generate_default_code(cr, uid, ctx),
        'brand_code': lambda s, cr, uid, ctx: 
            s.generate_default_code(cr, uid, ctx),
            
        'producer_category_id': lambda s, cr, uid, ctx: 
            s.generate_category_id(cr, uid, 'producer', ctx),
        'brand_category_id': lambda s, cr, uid, ctx: 
            s.generate_category_id(cr, uid, 'brand', ctx),
        'discount_category_id': lambda s, cr, uid, ctx: 
            s.generate_category_id(cr, uid, 'discount', ctx),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

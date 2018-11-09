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

class MetelPriceRule(orm.Model):
    """ Model name: Metel Price Rule
    """
    
    _name = 'metel.price.rule'
    _description = 'METEL price rule'
    _rec_name = 'group_id'
    _order = 'group_id'

    _columns = {
        'group_id': fields.many2one(
            'product.category', 'Category', required=True),
        'mode': fields.selection([
            ('brand', 'Brand'),
            ('statistic', 'Statistic'),
            ], 'Mode', required=True),
        }
    
    _defaults = {
        'mode': lambda *x: 'mode',
        }

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'
    
    # Pricelist multi discount:
    def onchange_metel_net_force_scale(self, cr, uid, ids, 
            discount_rates, context=None):
        ''' Update calc value, reformat text
        '''        
        res = self.format_multi_discount(discount_rates)
        return {
            'value': {
                'metel_net_force_perc': res['value'],
                'metel_net_force_scale': res['text'],
                }}    

    def onchange_metel_sale_force_scale(self, cr, uid, ids, 
            discount_rates, context=None):
        ''' Update calc value, reformat text
        '''        
        res = self.format_multi_discount(discount_rates)
        return {
            'value': {
                'metel_sale_force_perc': res['value'],
                'metel_sale_force_scale': res['text'],
                }}    

    # Utility function for compute text and value
    def format_multi_discount(self, multi_discount):
        ''' Manage multi discount: text like: 50%+30%
            return {'text': '50.0% + 30.0%', 'value': 65.00}
        '''
        res = {'value': 0.0, 'text': ''}
        if not multi_discount:
            return res
           
        disc = \
            multi_discount.replace(' ', '').replace(',', '.').replace('%', '')

        discount_list = disc.split('+')
        base_discount = 100.0
        for rate in discount_list:
            try:
                i = eval(rate)
            except:
                i = 0.00
            base_discount -= base_discount * i / 100.0
        res['value'] = 100.0 - base_discount
        res['text'] = ' + '.join(discount_list)
        return res

    def metel_product_return(self, cr, uid, ids, context=None):
        ''' Metel cost view
        '''
        #model_pool = self.pool.get('ir.model.data')
        #form_view_id = False,#model_pool.get_object_reference(
        #    cr, uid, 
        #    'metel_pricelist', 
        #    'view_product_product_metel_pricelist_form',
        #    )[1]
    

        return {
            'type': 'ir.actions.act_window',
            'name': _('Product detail'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': ids[0],
            'res_model': 'product.product',
            #'view_id': form_view_id,
            'views': [(False, 'form'), (False, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }
    
    def metel_cost_management(self, cr, uid, ids, context=None):
        ''' Metel cost view
        '''
        model_pool = self.pool.get('ir.model.data')
        form_view_id = model_pool.get_object_reference(
            cr, uid, 
            'metel_pricelist', 
            'view_product_product_metel_pricelist_form',
            )[1]
    
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cost mode'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_id': ids[0],
            'res_model': 'product.product',
            'view_id': form_view_id,
            'views': [(form_view_id, 'form'), (False, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    # -------------------------------------------------------------------------
    # Fields function:
    # -------------------------------------------------------------------------
    def _get_metel_price_data(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''    
        res = {}
        return res
        for product in self.browse(cr, uid, ids, context=context):
            res[product.id] = {
                'metel_net': 0.0,
                'metel_net_vat': 0.0,
                
                'metel_sale': 0.0,
                'metel_sale_vat': 0.0,
                
                'lst_price_vat': 0.0,
                'standard_price_vat': 0.0,
                }
        return res

    _columns = {    
        # Net price:
        'metel_net_force': fields.float(
            'METEL Net force', 
            digits_compute=dp.get_precision('Product Price')),
        'metel_net_force_scale': fields.char(
            'METEL Net scale %', size=20),
        'metel_net_force_perc': fields.float(
            'METEL Net force %', digits=(16, 8),
            ),
        'metel_net': fields.function(
            _get_metel_price_data, method=True, 
            type='float', string='Net', multi=True,
            ), 
        'metel_net_vat': fields.function(
            _get_metel_price_data, method=True, 
            type='float', string='Net VAT', multi=True,
            ), 

        # Sale price:    
        'metel_sale_force': fields.float(
            'METEL Sale force',
            digits_compute=dp.get_precision('Product Price')),
        'metel_sale_force_scale': fields.char(
            'METEL Net scale %', size=20),
        'metel_sale_force_perc': fields.float(
            'METEL Sale force %', digits=(16, 8),
            ),
        'metel_sale': fields.function(
            _get_metel_price_data, method=True, 
            type='float', string='Sale', multi=True,
            ), 
        'metel_sale_vat': fields.function(
            _get_metel_price_data, method=True, 
            type='float', string='Sale VAT', multi=True,
            ), 
    
        # VAT product:            
        'lst_price_vat': fields.function(
            _get_metel_price_data, method=True, 
            type='float', string='Last VAT', multi=True,
            digits_compute=dp.get_precision('Product Price'),
            ),
        'standard_price_vat': fields.function(
            _get_metel_price_data, method=True, 
            type='float', string='METEL VAT', multi=True,
            ), 
        
        #'metel_sale': fields.function( >>> use lst_price
        #    _get_metel_price_data, method=True, 
        #    type='float', string='Net', 
        #    multi=True), 

        #'metel_last_load': fields.float( >>> use standard_cost
        #    'Last price', digits=(16, 3)),
        #    ),        
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

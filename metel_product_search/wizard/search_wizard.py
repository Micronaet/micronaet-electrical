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


class MetelProductSearchWizard(orm.TransientModel):
    ''' Wizard for metel product
    '''
    _name = 'metel.product.search.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_search(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        
        
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        model_pool = self.pool.get('ir.model.data')
        #view_id = model_pool.get_object_reference(
        #    'module_name', 'view_name')[1]
        form_id = tree_id = False
        
        product_pool = self.pool.get('product.product')
        
        # Domain creation:
        domain = []
        
        # Char field:
        if wiz_proxy.start:
            domain.append(('default_code', '=ilike', '%s%%' % wiz_proxy.start))
        if wiz_proxy.end:
            domain.append(('default_code', '=ilike', '%%%s' % wiz_proxy.end))
        if wiz_proxy.code:     
            domain.append(('default_code', 'ilike', wiz_proxy.code))
        if wiz_proxy.name:   
            domain.append(('name', 'ilike', wiz_proxy.name))
        if wiz_proxy.ean13:   
            domain.append(('ean13', 'ilike', wiz_proxy.ean13))
            
        # Relational field:
        if wiz_proxy.metel_producer_id:
            domain.append(
                ('metel_producer_id', '=', wiz_proxy.metel_producer_id.id))        
        if wiz_proxy.metel_brand_id:
            domain.append(
                ('metel_brand_id', '=', wiz_proxy.metel_brand_id.id))
        if wiz_proxy.metel_serie_id:
            domain.append(
                ('metel_serie_id', '=', wiz_proxy.metel_serie_id.id))            
        if wiz_proxy.categ_id:
            domain.append(
                ('categ_id', '=', wiz_proxy.categ_id.id))

        product_ids = product_pool.search(cr, uid, domain, context=context)
        if not product_ids:
            raise osv.except_osv(
                _('Error'), 
                _('Product not found!'),
                )
        elif len(product_ids) > 1:
            # Tree mode:
            view_mode = 'tree,form'
            views = [(tree_id, 'tree'), (tree_id, 'form')]
        else:    
            # Form mode:
            view_mode = 'form,tree'
            views = [(tree_id, 'form'), (tree_id, 'tree')]
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Result for view_name'),
            'view_type': 'form',
            'view_mode': view_mode,
            'res_id': product_ids[0],
            'res_model': 'product.product',
            #'view_id': view_id, # False
            'views': views,
            'domain': [('id', 'in', product_ids)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    _columns = {
        'start': fields.char('Product code start', size=64),
        'end': fields.char('Product code end', size=64),
        'code': fields.char('Product code', size=64),
        'name': fields.char('Product name', size=64),
        'ean13': fields.char('EAN 13', size=13),
        
        'metel_producer_id': fields.many2one(
            'product.category', 'Metel producer'),
        'metel_brand_id': fields.many2one(
            'product.category', 'Metel brand'),
        'metel_serie_id': fields.many2one(
            'product.category', 'Metel serie'),
        'categ_id': fields.many2one(
            'product.category', 'Electrocod'),
        }
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

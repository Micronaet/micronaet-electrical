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

class AccountAnalyticAccount(orm.Model):
    """ Model name: AccountAnalyticAccount
    """
    
    _inherit = 'account.analytic.account'
    
    def get_detail_account_cost(self, cr, uid, ids, context=None):
        ''' Return cost view:
        '''
        model_pool = self.pool.get('ir.model.data')
        view_id = model_pool.get_object_reference(
            cr, uid, 
            'electrical_account_stats', 
            'view_account_analytic_account_cost_form',
            )[1]
    
        return {
            'type': 'ir.actions.act_window',
            'name': _('Account details'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'res_model': 'account.analytic.account',
            'view_id': view_id, # False
            'views': [(view_id, 'form'),(False, 'tree')],
            'domain': [('id', '=', ids[0])],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    def _get_statinfo_intervent(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate intervent
        '''
        res = {}
        intervent_pool = self.pool.get('hr.analytic.timesheet')
        
        for account in self.browse(cr, uid, ids, context=context):
            res[account.id] = len(
                intervent_pool.search(cr, uid, [
                    ('account_id', '=', account.id),
                    ], context=context))
        return res
        
    def _get_statinfo_move(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate  move
        '''
        res = {}
        move_pool = self.pool.get('stock.move')
        
        for account in self.browse(cr, uid, ids, context=context):
            res[account.id] = len(
                move_pool.search(cr, uid, [
                    ('picking_id.account_id', '=', account.id),
                    ], context=context))
        return res

    def _get_statinfo_picking(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        picking_pool = self.pool.get('stock.picking')
        
        for account in self.browse(cr, uid, ids, context=context):
            res[account.id] = len(
                picking_pool.search(cr, uid, [
                    ('account_id', '=', account.id),
                    ], context=context))
        return res

    def _get_statinfo_complete(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        if len(ids) > 1:
            return res

        account_id = ids[0]
        res = {account_id: ''}

        # Pool used:
        picking_pool = self.pool.get('stock.picking')
        timesheet_pool = self.pool.get('hr.analytic.timesheet')
        
        # ---------------------------------------------------------------------
        # Picking analysis:
        # ---------------------------------------------------------------------
        picking_ids = picking_pool.search(cr, uid, [
            ('account_id', '=', account_id),
            ], context=context)
        
        data_mask = '''
            <tr>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
            </tr>'''

        # Table startup:
        res[account_id] += '<table>'

        # Header:
        res[account_id] += '''
            <tr>
                <th colspan="5">Consegne materiale: %s</th>
            </tr>            
            <tr>
                <th>Descrizione</th>
                <th>Errori</th>
                <th>Ricavo</th>
                <th>Costo</th>
                <th>Utile</th>
            </tr>''' % len(picking_ids)
        
        total = {
            'cost': 0.0,
            'revenue': 0.0,
            'error': 0,
            }

        # TODO manage also state of picking:    
        for picking in picking_pool.browse(
                cr, uid, picking_ids, context=context):                 
            for move in picking.move_lines:
                if not move.product_id:
                    continue
                qty = move.product_uom_qty
                cost = qty * move.product_id.standard_price
                revenue = qty * move.price_unit
                if not cost or not revenue:
                    total['error'] += 1
                    
                total['cost'] += cost
                total['revenue'] += revenue

        material_amount = total['revenue'] - total['cost']
        res[account_id] += data_mask % (
            'Materiale:',
            total['error'],
            total['cost'],
            total['revenue'],
            material_amount,
            )
                    
        # ---------------------------------------------------------------------
        # Intervent:
        # ---------------------------------------------------------------------
        timesheet_ids = timesheet_pool.search(cr, uid, [
            ('account_id', '=', account_id),
            ], context=context)
        
        # Header:
        res[account_id] += '''
            <tr>
                <th colspan="5">Interventi totali: %s</th>
            </tr>            
            <tr>
                <th>Descrizione</th>
                <th>H.</th>
                <th>Ricavo</th>
                <th>Costo</th>
                <th>Utile</th>
            </tr>''' % len(timesheet_ids)
            
        total = {
            'hour': 0.0,
            'cost': 0.0,
            'revenue': 0.0,
            #'error': 0,
            }

        # TODO manage also state of picking:    
        for ts in timesheet_pool.browse(
                cr, uid, timesheet_ids, context=context):
            total['hour'] += ts.unit_amount
            total['cost'] += 0.0 # TODO
            total['revenue'] += 0.0 # TODO 

        ts_amount = total['revenue'] - total['cost']
        res[account_id] += data_mask % (
            'Interventi:',
            total['hour'],
            total['cost'],
            total['revenue'],
            ts_amount,
            )

        res[account_id] += data_mask % (
            'Riepilogo:',
            '',
            '',
            material_amount,
            ts_amount,
            )
        res[account_id] += '<table>'

        return res
        
    _columns = {
        'statinfo_intervent': fields.function(
            _get_statinfo_intervent, method=True, 
            type='integer', string='# of intervent'), 
        'statinfo_move': fields.function(
            _get_statinfo_move, method=True, 
            type='integer', string='# of move'), 
        'statinfo_picking': fields.function(
            _get_statinfo_picking, method=True, 
            type='integer', string='# of picking'), 
        'statinfo_complete': fields.function(
            _get_statinfo_complete, method=True, 
            type='text', string='Complete stats'), 
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

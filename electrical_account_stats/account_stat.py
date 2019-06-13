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
        
        total = { 
            # [Cost, Revenue, Gain, Error]
            'picking': : [0.0, 0.0, 0.0, 0.0, 0],
            'ddt': [0.0, 0.0, 0.0, 0],
            'invoice': [0.0, 0.0, 0.0, 0],

            # [Cost, Revenue, Gain, Hour]
            'intervent': [0.0, 0.0, 0.0, 0.0],
            'intervent_invoiced': [0.0, 0.0, 0.0, 0.0],
            }

        # ---------------------------------------------------------------------
        # Common Header:
        # ---------------------------------------------------------------------
        data_mask = '''
            <tr class='table_bf'>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
            </tr>'''

        summary_mask = '''
            <tr class='table_bf'>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
            </tr>'''

        res[account_id] += '''
            <style>
                .table_bf {
                     border:1px 
                     padding: 3px;
                     solid black;
                 }
                .table_bf td {
                     border:1px 
                     solid black;
                     padding: 3px;
                     text-align: center;
                 }
                .table_bf th {
                     border:1px 
                     solid black;
                     padding: 3px;
                     text-align: center;
                     background-color: grey;
                     color: white;
                 }
            </style>
            '''
            
        # ---------------------------------------------------------------------
        # Picking analysis:
        # ---------------------------------------------------------------------
        picking_ids = picking_pool.search(cr, uid, [
            ('account_id', '=', account_id),
            ('pick_move', '=', 'out'), # Only out movement
            ], context=context)
        picking    
        if picking_ids:    
            # Header:
            res[account_id] += '''
                <p>Consegne materiali: [Tot.: %s]</p>
                <table class='table_bf'>
                <tr class='table_bf'>
                    <th>Descrizione</th>
                    <th>Errori</th>
                    <th>Ricavo</th>
                    <th>Costo</th>
                    <th>Utile</th>
                </tr>''' % len(picking_ids)
            
            # TODO manage also state of picking:    
            for picking in picking_pool.browse(
                    cr, uid, picking_ids, context=context):                 
                if picking.ddt_id:
                    if picking.ddt_id.is_invoiced:
                        mode = 'invoice'
                    else:
                        mode = 'ddt'
                else:        
                    mode = 'picking'

                for move in picking.move_lines:
                    if not move.product_id:
                        continue
                    qty = move.product_uom_qty
                    
                    # TODO Get correct price:
                    cost = qty * move.product_id.standard_price
                    revenue = qty * move.price_unit

                    if not cost or not revenue:
                        total[mode][3] += 1 # error
                        
                    total[mode][0] += cost
                    total[mode][1] += revenue

            for mode, name in (('picking', 'Consegne'), ('ddt', 'DDT'), 
                    ('invoice', 'Fatture')):
                    
                total[mode][3] = total[mode][1] - total[mode][0]
                res[account_id] += data_mask % (
                    name,
                    total[mode][3], # error
                    total[mode][0], # cost
                    total[mode][1], # revenue
                    total[mode][2], # gain
                    )
            res[account_id] += '''</table><br/>'''
        else:
            material_amount = 0.0
            res[account_id] += '''<p>Consegne materiale: Non presenti!</p>'''

        # ---------------------------------------------------------------------
        # Intervent:
        # ---------------------------------------------------------------------
        timesheet_ids = timesheet_pool.search(cr, uid, [
            ('account_id', '=', account_id),
            ], context=context)
        
        if timesheet_ids:
            # Header:
            res[account_id] += '''
                <p>Interventi totali: [Tot.: %s]</p>
                <table class='table_bf'>
                <tr class='table_bf'>
                    <th>Descrizione</th>
                    <th>H.</th>
                    <th>Ricavo</th>
                    <th>Costo</th>
                    <th>Utile</th>
                </tr>''' % len(timesheet_ids)
                
            # TODO manage also state of picking:    
            for ts in timesheet_pool.browse(
                    cr, uid, timesheet_ids, context=context):
                if ts.is_invoiced:
                    mode = 'intervent_invoiced':
                else:
                    mode = 'intervent'
                    
                total[mode][3] += ts.unit_amount
                total[mode][0] += 0.0 # TODO cost
                total[mode][1] += 0.0 # TODO revenue

            for mode, name in (('intervent', 'Interventi da fatturare'), 
                    ('intervent_invoiced', 'Interventi fatturati')):
                total[mode][2] = total[mode][1] - total[mode][0]
                
                res[account_id] += data_mask % (
                    name,
                    total[mode][3], # hour
                    total[mode][0], # cost
                    total[mode][1], # revenut
                    total[mode][2], # gain
                    )
            res[account_id] += '''</table><br/>'''
        else:
            ts_amount = 0.0
            res[account_id] += '''<p>Interventi: Non presenti!</p>'''

        # ---------------------------------------------------------------------
        # Summary block:
        # ---------------------------------------------------------------------
        res[account_id] += '''
            <p>Riepilogo:</p>
            <table class='table_bf'>
                <tr class='table_bf'>
                    <th>Descrizione</th>                    
                    <th>Ricavo</th>
                    <th>Costo</th>
                    <th>Utile</th>
                </tr>'''

        # TODO add correct value:
        
        # Not Invoiced:
        res[account_id] += summary_mask % (
            'Not fatturato',
            total['picking'][1] + total['ddt'][1] + total['intervent'][1],
            total['picking'][0] + total['ddt'][0] + total['intervent'][0],
            total['picking'][2] + total['ddt'][2] + total['intervent'][2],
            )

        # Invoiced:
        res[account_id] += summary_mask % (
            'Fatturato',
            total['invoice'][1] + total['intervent_invoiced'][1],
            total['invoice'][0] + total['intervent_invoiced'][0],
            total['invoice'][2] + total['intervent_invoiced'][2],
            )

        # Totale:
        res[account_id] += summary_mask % (
            'Totale',
            total['picking'][1] + total['ddt'][1] + total['intervent'][1] +\
            total['invoice'][1] + total['intervent_invoiced'][1],
            
            total['picking'][0] + total['ddt'][0] + total['intervent'][0] +\
            total['invoice'][0] + total['intervent_invoiced'][0],
            
            total['picking'][2] + total['ddt'][2] + total['intervent'][2] +\
            total['invoice'][2] + total['intervent_invoiced'][2],
            )
            
        res[account_id] += '</table>'

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

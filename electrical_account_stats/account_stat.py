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
import locale
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
        """ Return cost view:
        """
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
            'view_id': view_id,  # False
            'views': [(view_id, 'form'), (False, 'tree')],
            'domain': [('id', '=', ids[0])],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    def _get_statinfo_intervent(
            self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate intervent
        """
        res = {}
        intervent_pool = self.pool.get('hr.analytic.timesheet')

        for account in self.browse(cr, uid, ids, context=context):
            res[account.id] = len(
                intervent_pool.search(cr, uid, [
                    ('account_id', '=', account.id),
                    ], context=context))
        return res

    def _get_statinfo_move(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate  move
        """
        res = {}
        move_pool = self.pool.get('stock.move')

        for account in self.browse(cr, uid, ids, context=context):
            res[account.id] = len(
                move_pool.search(cr, uid, [
                    ('picking_id.account_id', '=', account.id),
                    ], context=context))
        return res

    def _get_statinfo_picking(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        picking_pool = self.pool.get('stock.picking')

        for account in self.browse(cr, uid, ids, context=context):
            res[account.id] = len(
                picking_pool.search(cr, uid, [
                    ('account_id', '=', account.id),
                    ], context=context))
        return res

    def _get_statinfo_complete(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def number_cell(value, negative='never', positive=False, bold=False):
            """ Return cell block for number
                color: never, negative, empty
            """
            value = value or 0.0
            if bold:
                bold_on = '<b>'
                bold_off = '</b>'
            else:
                bold_on = bold_off = ''

            currency = ''
            for c in locale.currency(value, grouping=True):
                if ord(c) < 127:
                    currency += c

            if positive and value > 0.0:  # #fcfc92
                number_class = 'td_number_green'
            elif negative == 'empty' and value <= 0.0:  # #fcfc92
                number_class = 'td_number_red'
            elif negative == 'negative' and value < 0.0:
                number_class = 'td_number_red'
            else:
                number_class = 'td_number'

            return '<td class="td_text %s">%s%s%s</td>' % (
                number_class,
                bold_on,
                currency,
                bold_off,
                )

        # ---------------------------------------------------------------------
        #                             Procedure
        # ---------------------------------------------------------------------
        # Pool used:
        picking_pool = self.pool.get('stock.picking')
        timesheet_pool = self.pool.get('hr.analytic.timesheet')
        expence_pool = self.pool.get('account.analytic.expence')
        product_pool = self.pool.get('product.product')
        mode_pool = self.pool.get('hr.intervent.user.mode')

        # ---------------------------------------------------------------------
        # Common Header:
        # ---------------------------------------------------------------------
        css_block = '''
            <style>
                .table_bf {
                     border: 1px solid black;
                     padding: 3px;
                     solid black;
                     }
                .table_bf .td_number {
                     text-align: right;
                     border: 1px solid black;
                     padding: 3px;
                     width: 70px;
                     }
                .table_bf .td_number_red {
                     text-align: right;
                     border: 1px solid black;
                     padding: 3px;
                     width: 70px;
                     background-color: #ffb8b8;
                     }
                .table_bf .td_number_green {
                     text-align: right;
                     border: 1px solid black;
                     padding: 3px;
                     width: 70px;
                     background-color: #9cffb1;
                     }
                .table_bf .td_text {
                     text-align: right;
                     border: 1px solid black;
                     padding: 3px;
                     width: 80px;
                     }
                .table_bf th {
                     text-align: center;
                     border: 1px solid black;
                     padding: 3px;
                     background-color: grey;
                     color: white;
                     }
            </style>
            '''
        res = {}
        for account in self.browse(cr, uid, ids, context=context):
            account_id = account.id
            res[account_id] = {
                'statinfo_complete': '',
                'statinfo_summary': '',
                }  # XXX Update after for other data

            total = {
                # [Cost, Revenue, Gain, Error]
                'picking': [0.0, 0.0, 0.0, 0.0, 0],
                'ddt': [0.0, 0.0, 0.0, 0],
                'invoice': [0.0, 0.0, 0.0, 0],
                'account_invoice': [0.0, 0.0, 0.0, 0],

                # [Cost, Revenue, Gain, Hour]
                'intervent': [0.0, 0.0, 0.0, 0.0],
                'intervent_invoiced': [0.0, 0.0, 0.0, 0.0],

                'expence': [0.0, 0.0, 0.0],  # NOTE only cost!
                }

            # -----------------------------------------------------------------
            # Pre load data:
            # -----------------------------------------------------------------
            partner = account.partner_id
            partner_forced = {}
            for forced in partner.mode_revenue_ids:
                partner_forced[forced.mode_id.id] = forced.list_price

            # Load mode pricelist (to get revenue):
            mode_pricelist = {}
            mode_ids = mode_pool.search(cr, uid, [], context=context)
            for mode in mode_pool.browse(
                    cr, uid, mode_ids, context=context):
                mode_pricelist[mode.id] = mode.list_price

            res[account_id]['statinfo_complete'] += css_block
            res[account_id]['statinfo_summary'] += css_block

            # -----------------------------------------------------------------
            # Picking analysis:
            # -----------------------------------------------------------------
            picking_ids = picking_pool.search(cr, uid, [
                ('account_id', '=', account_id),
                ('pick_move', '=', 'out'),  # Only out movement
                ], context=context)
            if picking_ids:
                # TODO manage also state of picking:
                pickings = picking_pool.browse(
                    cr, uid, picking_ids, context=context)
                partner = pickings[0].partner_id
                activity_price = partner.activity_price

                # Header:
                res[account_id]['statinfo_complete'] += '''
                    <p>
                    <b>Consegne materiali (Ricavo usa: %s)</b>: [Tot.: %s]
                    </p>
                    <table class='table_bf'>
                    <tr class='table_bf'>
                        <th>Descrizione</th>
                        <th>Costo</th>
                        <th>Ricavo</th>
                        <th>Utile</th>
                        <th>Errori</th>
                    </tr>''' % (activity_price, len(picking_ids))
                for picking in pickings:
                    if picking.ddt_id:
                        if picking.ddt_id.is_invoiced:
                            mode = 'invoice'
                            total['account_invoice'][1] += \
                                picking.ddt_id.invoice_amount
                        else:
                            mode = 'ddt'
                    else:
                        mode = 'picking'

                    for move in picking.move_lines:
                        product = move.product_id
                        if not product:
                            continue
                        qty = move.product_qty  # _uom

                        '''
                        reply = product_pool.extract_product_data(
                            cr, uid, move, context=context)
                        (product_name, list_price, standard_price,
                            discount_price, discount_vat) = reply
                        if activity_price == 'lst_price':
                            price = list_price
                        else: # metel_sale
                            price = discount_price
                        '''
                        (product_name, list_price, standard_price,
                            discount_price, discount_vat) = \
                            product_pool.extract_product_data(
                                cr, uid, move, context=context)

                        # cost = qty * product.standard_price
                        # XXX Not as in report:
                        # revenue = qty * product.lst_price

                        cost = qty * standard_price
                        revenue = qty * list_price
                        # or move.price_unit
                        # ex.: price # move.price_unit

                        if not cost or not revenue:
                            total[mode][3] += 1  # error

                        total[mode][0] += cost
                        total[mode][1] += revenue

                for mode, name in (
                        ('picking', 'Consegne'),
                        ('ddt', 'DDT'),
                        ('invoice', 'Fatture'),
                        ('account_invoice', 'Gestionale')):

                    total[mode][2] = total[mode][1] - total[mode][0]
                    res[account_id]['statinfo_complete'] += '''
                        <tr class='table_bf'>
                            <td class="td_text">%s</td>%s%s%s%s
                        </tr>''' % (
                            name,
                            number_cell(total[mode][0]),  # cost
                            number_cell(total[mode][1]),  # revenue
                            number_cell(total[mode][2]),  # gain
                            number_cell(total[mode][3]),  # error
                            )
                res[account_id]['statinfo_complete'] += '''</table><br/>'''
            else:
                res[account_id]['statinfo_complete'] += '''
                    <p><b>Consegne materiale</b>:<br/> Non presenti!</p>'''

            # -----------------------------------------------------------------
            # Intervention:
            # -----------------------------------------------------------------
            timesheet_ids = timesheet_pool.search(cr, uid, [
                ('account_id', '=', account_id),
                ('not_in_report', '=', False),
                ], context=context)

            if timesheet_ids:
                # Header:
                res[account_id]['statinfo_complete'] += '''
                    <p><b>Interventi totali</b>: [Tot.: %s]</p>
                    <table class='table_bf'>
                    <tr class='table_bf'>
                        <th>Descrizione</th>
                        <th>Costo</th>
                        <th>Ricavo</th>
                        <th>Utile</th>
                        <th>H.</th>
                    </tr>''' % len(timesheet_ids)

                # todo manage also state of picking:
                for ts in timesheet_pool.browse(
                        cr, uid, timesheet_ids, context=context):
                    if ts.is_invoiced:
                        mode = 'intervent_invoiced'
                    else:
                        mode = 'intervent'

                    # Read revenue:
                    user_mode_id = ts.user_mode_id.id
                    if user_mode_id in partner_forced:  # partner forced
                        unit_revenue = partner_forced[user_mode_id]
                    else:  # read for default list:
                        unit_revenue = mode_pricelist.get(user_mode_id, 0.0)

                    total[mode][0] -= ts.amount  # Always negative
                    total[mode][1] += ts.unit_amount * unit_revenue  # revenue
                    total[mode][3] += ts.unit_amount  # H.

                for mode, name in (('intervent', 'Da fatturare'),
                        ('intervent_invoiced', 'Fatturati')):
                    total[mode][2] = total[mode][1] - total[mode][0]

                    res[account_id]['statinfo_complete'] += '''
                        <tr class='table_bf'>
                            <td class="td_text">%s</td>%s%s%s%s
                        </tr>''' % (
                                name,
                                number_cell(total[mode][0]),  # cost
                                number_cell(total[mode][1]),  # revenue
                                number_cell(total[mode][2]),  # gain
                                number_cell(total[mode][3]),  # hour
                                )
                res[account_id]['statinfo_complete'] += '''</table><br/>'''
            else:
                res[account_id]['statinfo_complete'] += '''
                    <p><b>Interventi</b>:<br/>Non presenti!</p>'''

            # -----------------------------------------------------------------
            #                           Expences:
            # -----------------------------------------------------------------
            expence_ids = expence_pool.search(cr, uid, [
                ('account_id', '=', account_id),
                ('printable', '!=', 'none'),
                ], context=context)
            mode = 'expence'
            if expence_ids:
                # Header:
                res[account_id]['statinfo_complete'] += '''
                    <p><b>Spese totali</b>: [Tot.: %s]</p>
                    <table class='table_bf'>
                    <tr class='table_bf'>
                        <th>Descrizione</th>
                        <th>Costo</th>
                        <th>Ricavo</th>
                        <th>Utile</th>
                    </tr>''' % len(expence_ids)

                for expence in expence_pool.browse(
                        cr, uid, expence_ids, context=context):
                    total[mode][0] += expence.total
                    total[mode][1] += expence.total_forced or expence.total
                total[mode][2] = total[mode][1] - total[mode][0]

                res[account_id]['statinfo_complete'] += '''
                    <tr class='table_bf'>
                        <td class="td_text">Spese</td>%s%s%s
                    </tr>''' % (
                        number_cell(total[mode][0]), # cost
                        number_cell(total[mode][1]), # revenue
                        number_cell(total[mode][2]), # gain
                        )
                res[account_id]['statinfo_complete'] += '''</table><br/>'''

            else:
                res[account_id]['statinfo_complete'] += '''
                    <p><b>Spese</b>:<br/>Non presenti!</p>
                    '''
            res[account_id]['statinfo_complete'] += '</table>'

            # -----------------------------------------------------------------
            # Summary block:
            # -----------------------------------------------------------------
            total_summary = {
                'delivery': sum((
                    total['picking'][0],
                    total['ddt'][0],
                    total['invoice'][0],
                    )),
                'works': sum((
                    total['intervent'][0],
                    total['intervent_invoiced'][0],
                    )),
                'expence':
                    total['expence'][0],
                'hours': sum((
                    total['intervent'][3],
                    total['intervent_invoiced'][3],
                    ))
                }

            # Update other data:
            res[account_id]['statinfo_hour_done'] = total_summary['hours']
            res[account_id]['statinfo_hour_remain'] = account.total_hours - \
                total_summary['hours']

            res[account_id]['statinfo_invoiced'] = total['account_invoice'][1]
            res[account_id]['statinfo_remain_invoiced'] = \
                account.total_amount - total['account_invoice'][1]
            total_cost = sum(
                [total_summary[k] for k in total_summary if k != 'hours'])
            # Ex. total_summary.values())

            res[account_id]['statinfo_total_cost'] = - total_cost

            res[account_id]['statinfo_margin_nominal'] = \
                account.total_amount - total_cost
            res[account_id]['statinfo_margin_invoice'] = \
                total['account_invoice'][1] - total_cost

            res[account_id]['statinfo_summary'] += '''
                <table class='table_bf'>
                    <tr class='table_bf'>
                        <th>Descrizione</th>                    
                        <th>Costi</th>
                        <th>Totali</th>
                    </tr>

                    <tr class='table_bf'>
                        <td colspan="3" align="center"><b>Ore</b></td>
                    </tr>

                    <tr class='table_bf'>
                        <td class="td_text">Ore</td>
                        %s
                        %s
                    </tr>                
                    <tr class='table_bf'>
                        <td class="td_text"><b>Rimanenti</b></td>
                        <td class="td_text">&nbsp;</td>
                        %s
                    </tr>                

                    <tr class='table_bf'>
                        <td colspan="3" align="center"><b>Ricavi</b></td>
                    </tr>
                    
                    <tr class='table_bf'>
                        <td class="td_text">Nominale</td>                    
                        <td class="td_text">&nbsp;</td>
                        %s
                    </tr>
                    
                    <tr class='table_bf'>
                        <td class="td_text">Fatturato</td>                    
                        <td class="td_text">&nbsp;</td>
                        %s
                    </tr>

                    <tr class='table_bf'>
                        <td class="td_text"><b>Residuo</b></td>                    
                        <td class="td_text">&nbsp;</td>
                        %s
                    </tr>
                    
                    <tr class='table_bf'>
                        <td colspan="3" align="center"><b>Costi</b></td>
                    </tr>

                    <tr class='table_bf'>
                        <td class="td_text">Consegnato</td>                    
                        %s
                        <td class="td_text">&nbsp;</td>
                    </tr>
                    <tr class='table_bf'>
                        <td class="td_text">Lavori</td>                    
                        %s
                        <td class="td_text">&nbsp;</td>
                    </tr>
                    <tr class='table_bf'>
                        <td class="td_text">Spese</td>                    
                        %s
                        <td class="td_text">&nbsp;</td>
                    </tr>                

                    <tr class='table_bf'>
                        <td class="td_text"><b>Costi tot.</b></td>                    
                        <td class="td_text">&nbsp;</td>
                        %s
                    </tr>                

                    <tr class='table_bf'>
                        <td colspan="3" align="center"><b>Margini</b></td>
                    </tr>

                    <tr class='table_bf'>
                        <td class="td_text">Nominale</td>
                        <td class="td_text">&nbsp;</td>
                        %s
                    </tr>                
                    <tr class='table_bf'>
                        <td class="td_text">Fatturato</td>                    
                        <td class="td_text">&nbsp;</td>
                        %s
                    </tr>                
                    ''' % (
                        # Hours:
                        number_cell(total_summary['hours']),
                        number_cell(account.total_hours, negative='empty'),
                        number_cell(
                            res[account_id]['statinfo_hour_remain'],
                            negative='negative',
                            bold=True,
                            ),

                        # Account and Invoiced
                        number_cell(
                            account.total_amount,
                            negative='empty',
                            ),
                        number_cell(total['account_invoice'][1]),
                        number_cell(
                            res[account_id]['statinfo_remain_invoiced'],
                            negative='negative',
                            bold=True,
                            ),

                        # Costs:
                        number_cell(total_summary['delivery']),
                        number_cell(total_summary['works']),
                        number_cell(total_summary['expence']),

                        number_cell(res[account_id]['statinfo_total_cost']),

                        number_cell(
                            res[account_id]['statinfo_margin_nominal'],
                            negative='empty',
                            positive=True,
                            bold=True,
                            ),
                        number_cell(
                            res[account_id]['statinfo_margin_invoice'],
                            negative='empty',
                            positive=True,
                            bold=True,
                            ),
                        )
        return res

    def refresh_stats(self, cr, uid, ids, context=None):
        """ Refresh stats data
        """
        i = 0
        total = len(ids)
        for account in self.browse(cr, uid, ids, context=context):
            i += 1

            if i % 10 == 0:
                _logger.warning('Updating statistic account data: %s / %s' % (
                    i, total))

            # Update single record:
            self.write(cr, uid, [account.id], {
                'history_hour_done': account.statinfo_hour_done,
                'history_hour_remain': account.statinfo_hour_remain,
                'history_invoiced': account.statinfo_invoiced,
                'history_remain_invoiced': account.statinfo_remain_invoiced,
                'history_total_cost': account.statinfo_total_cost,
                'history_margin_nominal': account.statinfo_margin_nominal,
                'history_margin_invoice': account.statinfo_margin_invoice,
                }, context=context)
        return True

    def refresh_all_stats(self, cr, uid, ids, context=None):
        """ Refresh stats data
        """
        account_ids = self.search(cr, uid, [], context=context)
        return self.refresh_stats(cr, uid, account_ids, context=context)

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
            _get_statinfo_complete, method=True, multi=True,
            type='text', string='Dettaglio statistico'),
        'statinfo_summary': fields.function(
            _get_statinfo_complete, method=True, multi=True,
            type='text', string='Riepilogo statistico'),

        # Dynamic:
        'statinfo_hour_done': fields.function(
            _get_statinfo_complete, method=True, multi=True,
            type='float', string='Ore fatte'),
        'statinfo_hour_remain': fields.function(
            _get_statinfo_complete, method=True, multi=True,
            type='float', string='Ore fatte'),
        'statinfo_invoiced': fields.function(
            _get_statinfo_complete, method=True, multi=True,
            type='float', string='Fatturato'),
        'statinfo_remain_invoiced': fields.function(
            _get_statinfo_complete, method=True, multi=True,
            type='float', string='Residuo da fatt.'),
        'statinfo_total_cost': fields.function(
            _get_statinfo_complete, method=True, multi=True,
            type='float', string='Costo totale'),
        'statinfo_margin_nominal': fields.function(
            _get_statinfo_complete, method=True, multi=True,
            type='float', string='Margine nominale'),
        'statinfo_margin_invoice': fields.function(
            _get_statinfo_complete, method=True, multi=True,
            type='float', string='Margine fatturato'),

        # History:
        'history_hour_done': fields.float(
            'Ore fatte', digits=(16, 2)),
        'history_hour_remain': fields.float(
            'Ore residue', digits=(16, 2)),
        'history_invoiced': fields.float(
            'Fatturato', digits=(16, 2)),
        'history_remain_invoiced': fields.float(
            'Residuo da fatt.', digits=(16, 2)),
        'history_total_cost': fields.float(
            'Costo totale', digits=(16, 2)),
        'history_margin_nominal': fields.float(
            'Margine nominale', digits=(16, 2)),
        'history_margin_invoice': fields.float(
            'Margine fatturato', digits=(16, 2)),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

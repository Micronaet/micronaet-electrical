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


class ResPartnerActivityWizard(orm.TransientModel):
    ''' Wizard for partner activity
    '''
    _name = 'res.partner.activity.wizard'

    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------
    def action_print(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        

        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        partner_id = wiz_browse.partner_id.id # Mandatory:
        account_id = wiz_browse.account_id.id
        from_date = wiz_browse.from_date
        to_date = wiz_browse.to_date

        # ---------------------------------------------------------------------
        # Pool used:
        # ---------------------------------------------------------------------
        excel_pool = self.pool.get('excel.writer')
        
        # Account:
        picking_pool = self.pool.get('stock.picking')
        ddt_pool = self.pool.get('stock.ddt')
        invoice_pool = self.pool.get('account.invoice')
        account_pool = self.pool.get('account.analytic.account')

        # Interventi:
        intervent_pool = self.pool.get('hr.analytic.timesheet')
        
        # ---------------------------------------------------------------------
        #                          COLLECT DATA:
        # ---------------------------------------------------------------------
        account_used = []

        # ---------------------------------------------------------------------
        # A. STOCK MATERIAL:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('partner_id', '=', partner_id),
            ('min_date', '>=', '%s 00:00:00' % from_date),
            ('min_date', '<=', '%s 23:59:59' % to_date),
            ('ddt_id', '=', False), # Not DDT
            ]
        if account_id:
            domain.append(('account_id', '=', account_id))
        picking_ids = picking_pool.search(cr, uid, domain, context=context)
        picking_proxy = picking_pool.browse(
            cr, uid, picking_ids, context=context)
        picking_db = {}
        for picking in picking_proxy:
            key = (
                picking.pick_state, 
                #picking.partner_id.name,
                picking.account_id.name,
                )
            if key not in picking_db:
                picking_db[key] = []
            picking_db[key].append(picking)

        # ---------------------------------------------------------------------
        # B. DDT MATERIAL:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('partner_id', '=', partner_id),
            ('delivery_date', '>=', '%s 00:00:00' % from_date),
            ('delivery_date', '<=', '%s 23:59:59' % to_date),
            ('invoice_id', '=', False), # Not Invoiced
            ]
        if account_id:
            domain.append(('account_id', '=', account_id))
        ddt_ids = ddt_pool.search(cr, uid, domain, context=context)
        ddt_proxy = ddt_pool.browse(
            cr, uid, ddt_ids, context=context)
        ddt_db = {}
        for ddt in ddt_proxy:
            key = (
                #ddt.partner_id.name,
                ddt.account_id.name,
                ddt.name,
                )
            if key not in ddt_db:
                ddt_db[key] = []
            ddt_db[key].append(ddt)

        # ---------------------------------------------------------------------
        # C. INVOICED MATERIAL:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('partner_id', '=', partner_id),
            ('date_invoice', '>=', from_date),
            ('date_invoice', '<=', to_date),
            ]
        if account_id:
            domain.append(('analytic_id', '=', account_id))
        invoice_ids = invoice_pool.search(cr, uid, domain, context=context)
        invoice_proxy = invoice_pool.browse(
            cr, uid, invoice_ids, context=context)
        invoice_db = {}
        for invoice in invoice_proxy:
            key = (
                #invoice.partner_id.name,
                invoice.account_id.name,
                invoice.number, 
                )
            if key not in invoice_db:
                invoice_db[key] = []
            invoice_db[key].append(invoice)

        # ---------------------------------------------------------------------
        # D. INTERVENT:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('intervent_partner_id', '=', partner_id),
            ('date_start', '>=', from_date),
            ('date_start', '<=', to_date),
            #('account_id.is_extra_report', '=', False),
            ]
        if account_id:
            domain.append(('account_id', '=', account_id))
        intervent_ids = intervent_pool.search(cr, uid, domain, context=context)
        intervent_proxy = intervent_pool.browse(
            cr, uid, intervent_ids, context=context)
        intervent_db = {}
        for intervent in intervent_proxy:
            key = (
                #intervent.intervent_partner_id.name,
                intervent.account_id.name,
                intervent.ref, 
                )
            if key not in intervent_db:
                intervent_db[key] = []
            intervent_db[key].append(intervent)

        # ---------------------------------------------------------------------
        # E. ACCOUNT:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('partner_id', '=', partner_id),
            ]
        if account_id:
            domain.append(('account_id', '=', account_id))
        account_ids = account_pool.search(cr, uid, domain, context=context)
        account_proxy = account_pool.browse(
            cr, uid, account_ids, context=context)
        account_db = {}
        for account in account_proxy:
            key = (
                #account.partner_id.name,
                account.account_mode,
                account.name,
                )
            if key not in account_db:
                account_db[key] = []
            account_db[key].append(account)

        # ---------------------------------------------------------------------
        #                             EXCEL REPORT:
        # ---------------------------------------------------------------------
        sheets = {
            # -----------------------------------------------------------------
            # Summary sheet:
            # -----------------------------------------------------------------
            'Riepilogo': { # Summary
                'row': 0,
                'header': [],
                'width': [],
                'data': True, # Create sheet
                },

            # -----------------------------------------------------------------
            # Sheet detail:
            # -----------------------------------------------------------------
            'Interventi': { # Invertent list
                'row': 0,
                'header': ['Commessa', 'Intervento', 'Utente'],
                'width': [35, 15, 20, ],
                'total': {},
                'cost': {},
                'data': intervent_db, 
                },   

            'Consegne': { # Picking to delivery
                'row': 0,
                'header': [
                    'Commessa', 'Picking', 'Data', 'Stato', 'Codice', 'UM', 
                    'Q.', 'Prezzo', 'Subtotale'],
                'width': [35, 15, 25, 20, 20, 15, 10, 10, 15, ],
                'total': {},
                'data': picking_db, 
                },   

            'DDT': { # DDT not invoiced
                'row': 0,
                'header': [
                    'Commessa', 'DDT', 'Data', 'Codice', 'UM', 'Q.', 'Prezzo', 
                    'Subtotale'],
                'width': [35, 15, 20, 25, 10, 15, 15, 20, ],
                'total': {},
                'data': ddt_db, 
                },

            'Fatture': { # Invoiced document
                'row': 0,
                'header': [
                    'Commessa', 'Fattura', 'Data', 'Posizione', 'Articolo', 
                    'UM', 'Q.', 'Prezzo', 'Sconto', 'Subtotale', 
                    #'Costo',
                    ],
                'width': [35, 15, 15, 20, 20, 10, 10, 10, 10, 15, ],
                'total': {},
                'cost': {},
                'data': invoice_db, 
                },   

            'Commesse': { # Account
                'row': 0,
                'header': ['Fatturazione', 'Codice', 'Commessa', 'Padre', 'Data', 
                    'Posizione fiscale', 'Ore', 'Stato'],
                'width': [25, 10, 30, 20, 15, 20, 10, 10],
                'data': account_db, 
                },                

            }
        sheet_order = [
            'Riepilogo', 'Interventi', 'Consegne', 'DDT', 'Fatture', 
            'Commesse',
            ]
        format_load = False # To update only first sheet creation:        
        for ws_name in sheet_order:
            sheet = sheets[ws_name]
            
            if not sheet['data']:
                continue # No sheet creation

            # Create sheet:
            excel_pool.create_worksheet(ws_name)

            # -----------------------------------------------------------------
            # Get used format:
            # -----------------------------------------------------------------
            if not format_load:
                format_load = True
                excel_pool.get_format()
                
                # -------------------------------------------------------------
                # Format list:
                # -------------------------------------------------------------
                f_title = excel_pool.get_format('title')
                f_header = excel_pool.get_format('header')
                f_text = excel_pool.get_format('text')
                f_number = excel_pool.get_format('number')

            # Setup columns
            excel_pool.column_width(ws_name, sheet['width'])
            
            # Print header
            excel_pool.write_xls_line(
                ws_name, sheet['row'], sheet['header'], 
                default_format=f_header)
            sheet['row'] += 1    
        
        # ---------------------------------------------------------------------
        # A. STOCK MATERIAL:
        # ---------------------------------------------------------------------
        ws_name = 'Consegne'
        sheet = sheets[ws_name]

        total = sheet['total']
        for key in picking_db:            
            for picking in picking_db[key]:
                account = picking.account_id
                account_id = account.id
                if account not in account_used:
                    account_used.append(account)

                if account_id not in total:
                    total[account_id] = 0.0
                if picking.move_lines:
                    if picking.move_lines:
                        for move in picking.move_lines:
                            try:
                                list_price = \
                                    move.product_id.metel_list_price
                            except:
                                list_price = 0.0    
                            subtotal = list_price * move.product_qty
                            
                            data = [  
                                # Header
                                picking.account_id.name or 'NON ASSEGNATA',
                                picking.name,
                                picking.min_date,
                                picking.pick_state,
                                
                                # Move:
                                move.product_id.default_code,
                                move.product_uom.name,
                                (move.product_qty, f_number),
                                (list_price, f_number),
                                (subtotal, f_number),
                                ]
                            # Total per account:                            
                            total[account_id] += subtotal
                            
                            excel_pool.write_xls_line(
                                ws_name, sheet['row'], data,
                                default_format=f_text)
                            sheet['row'] += 1

                    else: # Picking no movements:
                        data = [
                            # Header
                            picking.account_id.name or 'NON ASSEGNATA',
                            picking.name,
                            picking.min_date,
                            picking.pick_state,
                            
                            # Move:
                            'NESSUN MOVIMENTO',
                            '/',
                            (0.0, f_number),
                            (0.0, f_number),
                            (0.0, f_number),
                            ]
                        
                        excel_pool.write_xls_line(
                            ws_name, sheet['row'], data,
                            default_format=f_text)
                        sheet['row'] += 1
                            
        # ---------------------------------------------------------------------
        # B. DDT MATERIAL:
        # ---------------------------------------------------------------------
        ws_name = 'DDT'
        sheet = sheets[ws_name]
        total = sheet['total']
        for key in ddt_db:
            for ddt in ddt_db[key]:
                account = ddt.account_id
                account_id = account.id
                if account not in account_used:
                    account_used.append(account)
                if account_id not in total:
                    total[account_id] = 0.0                
                if ddt.picking_ids:
                    for picking in ddt.picking_ids:
                        if picking.move_lines:
                            for move in picking.move_lines:
                                try:
                                    list_price = \
                                        move.product_id.metel_list_price
                                except:
                                    list_price = 0.0    
                                subtotal = list_price * move.product_qty
                                
                                data = [  
                                    # Header
                                    ddt.account_id.name,
                                    ddt.name,
                                    ddt.delivery_date,
                                    
                                    # Move:
                                    move.product_id.default_code,
                                    move.product_uom.name,
                                    (move.product_qty, f_number),
                                    (list_price, f_number),
                                    (subtotal, f_number),
                                    ]
                                # Total per account:    
                                total[account_id] += subtotal
                                
                                excel_pool.write_xls_line(
                                    ws_name, sheet['row'], data,
                                    default_format=f_text)
                                sheet['row'] += 1

                        else: # Picking no movements:
                            data = [
                                # Header
                                ddt.account_id.name or 'NON ASSEGNATA',
                                ddt.name,
                                ddt.delivery_date,
                                
                                # Move:
                                'NESSUN MOVIMENTO',
                                '/',
                                (0.0, f_number),
                                (0.0, f_number),
                                (0.0, f_number),
                                ]
                            
                            excel_pool.write_xls_line(
                                ws_name, sheet['row'], data,
                                default_format=f_text)
                            sheet['row'] += 1
                else: # no 
                    data = [
                        # Header
                        ddt.account_id.name or 'NON ASSEGNATA',
                        ddt.name,
                        ddt.delivery_date,
                        
                        # Move:
                        'NESSUN PICKING',
                        '/',
                        (0.0, f_number),
                        (0.0, f_number),
                        (0.0, f_number),
                        ]
                    
                    excel_pool.write_xls_line(
                        ws_name, sheet['row'], data,
                        default_format=f_text)
                    sheet['row'] += 1

        # ---------------------------------------------------------------------
        # C. INVOICED MATERIAL:
        # ---------------------------------------------------------------------
        ws_name = 'Fatture'
        sheet = sheets[ws_name]

        total = sheet['total']
        cost = sheet['cost']
        for key in invoice_db:
            for invoice in invoice_db[key]:
                account = invoice.analytic_id
                account_id = account.id
                if account not in account_used:
                    account_used.append(account)

                if account_id not in total:
                    total[account_id] = 0.0                
                    cost[account_id] = 0.0                

                # -------------------------------------------------------------
                # Cost total from DDT linked:
                # -------------------------------------------------------------
                for ddt in invoice.ddt_ids:
                    if ddt.ddt_lines:
                        for move in ddt.ddt_lines:
                            try:
                                list_price = \
                                    move.product_id.metel_list_price
                            except:
                                list_price = 0.0    
                            subtotal = list_price * move.product_qty
                            cost[account_id] += subtotal

                # -------------------------------------------------------------
                # Invoice line:
                # -------------------------------------------------------------
                for line in invoice.invoice_line:
                    subtotal = line.price_subtotal#quantity * line.price_unit
                    data = [
                        # Header
                        invoice.analytic_id.name or 'NON ASSEGNATA',
                        invoice.number or 'BOZZA',
                        invoice.date_invoice,
                        invoice.fiscal_position.name,
                        
                        # Move:
                        line.product_id.default_code,
                        line.uos_id.name,
                        (line.quantity, f_number),
                        (line.price_unit, f_number),
                        (line.discount, f_number),
                        (subtotal, f_number),
                        ]
                    total[account_id] += subtotal
                    
                    excel_pool.write_xls_line(
                        ws_name, sheet['row'], data,
                        default_format=f_text)
                    sheet['row'] += 1

        # ---------------------------------------------------------------------
        # D. INTERVENT:
        # ---------------------------------------------------------------------
        ws_name = 'Interventi'
        sheet = sheets[ws_name]

        total = sheet['total']
        for key in intervent_db:        
            for intervent in intervent_db[key]:
                account = intervent.account_id
                account_id = account.id
                if account and account not in account_used:
                    account_used.append(account)

                if account_id not in total:
                    total[account_id] = 0.0
                    cost[account_id] = 0.0

                # TODO cost / revenue!!!
                this_cost = 0.0
                this_revenue = 0.0

                data = [
                    account.name or 'NON ASSEGNATA',
                    intervent.ref,
                    intervent.name,
                    intervent.mode,
                    intervent.operation_id.name,
                    intervent.user_id.name,
                    
                    # Intervent:
                    intervent.intervent_duration,
                    intervent.intervent_total,
                    intervent.unit_total,

                    # Extra hour:                    
                    intervent.trip_require,
                    intervent.trip_hour,                    
                    intervent.break_require,
                    intervent.break_hour,
                    
                    # Text:
                    intervent.intervention_request,
                    intervent.intervention,
                    intervent.intervention_note,
                    
                    # Revenue:
                    intervent.amount,
                    intervent.to_invoice,
                    intervent.not_in_report,
                    
                    intervent.state,
                    ]

                # Total per account:                            
                cost[account_id] += this_cost
                total[account_id] += this_revenue
                
                excel_pool.write_xls_line(
                    ws_name, sheet['row'], data,
                    default_format=f_text)
                sheet['row'] += 1

        # ---------------------------------------------------------------------
        # E. ACCOUNT:
        # ---------------------------------------------------------------------
        ws_name = 'Commesse'
        sheet = sheets[ws_name]

        # Block all account:
        for key in account_db:
            for account in account_db[key]:
                data = [
                    account.account_mode,
                    account.code,
                    account.name,
                    account.parent_id.name or '/',
                    account.from_date,
                    '/', #account.fiscal_position.name,
                    account.total_hours,
                    account.state,
                    ]
                
                excel_pool.write_xls_line(
                    ws_name, sheet['row'], data,
                    default_format=f_text)
                sheet['row'] += 1

        
        # Block account used:
        sheet['row'] += 2
        excel_pool.write_xls_line(
            ws_name, sheet['row'], ['Commesse toccate nel periodo:'],
            default_format=f_title)

        sheet['row'] += 1
        excel_pool.write_xls_line(
            ws_name, sheet['row'], sheet['header'],
            default_format=f_header)

        sheet['row'] += 1
        for account in account_used:   
            if not account:
                continue
            data = [
                account.account_mode,
                account.code,
                account.name,
                account.parent_id.name or '/',
                account.from_date,
                '/', #account.fiscal_position.name,
                account.total_hours,
                account.state,
                ]
            
            excel_pool.write_xls_line(
                ws_name, sheet['row'], data,
                default_format=f_text)
            sheet['row'] += 1

        # ---------------------------------------------------------------------
        # SUMMARY:
        # ---------------------------------------------------------------------
        ws_name = 'Riepilogo'
        sheet = sheets[ws_name]


        
        
        return excel_pool.return_attachment(
            cr, uid, 'partner_activity')

    _columns = {
        'partner_id': fields.many2one(
            'res.partner', 'Partner', required=True),
        'account_id': fields.many2one(
            'account.analytic.account', 'Account'),
        'from_date': fields.date('From date >= ', required=True),
        'to_date': fields.date('To date <', required=True),
        'float_time': fields.boolean('Formatted hour', 
            help='If checked print hour in HH:MM format'),
        }
        
    _defaults = {
        'float_time': lambda *x: True,
        'from_date': lambda *x: datetime.now().strftime('%Y-%m-01'),
        'to_date': lambda *x: (
            datetime.now() + relativedelta(months=1)).strftime('%Y-%m-01'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

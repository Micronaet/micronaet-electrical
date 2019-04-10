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

    def onchange_partner_private(self, cr, uid, ids, partner_id, context=None):
        ''' Change default discount and price for private report
        '''
        res = {}
        if not partner_id:
            return res
            
        partner_pool = self.pool.get('res.partner')
        partner = partner_pool.browse(cr, uid, partner_id, context=context)
        
        res['value'] = {
            'activity_material_discount': partner.activity_material_discount,
            'activity_price': partner.activity_price,
            }
        return res

    def data_mask_filter(self, data, mask):
        ''' data = list of data
            mask = bit list with 0 or 1 
            Using mask return data with value if 1 in the mask
        '''
        if not mask:
            return data    
        return [data[i] for i in range(0, len(data)) if mask[i:i + 1] != '0']

    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------
    def action_print_touched(self, cr, uid, ids, context=None):
        ''' List of partner touched in that period
        '''
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        from_date = wiz_browse.from_date
        to_date = wiz_browse.to_date
        
        # Intervent management:
        intervent_mode = wiz_browse.intervent_mode

        # ---------------------------------------------------------------------
        # Pool used:
        # ---------------------------------------------------------------------
        excel_pool = self.pool.get('excel.writer')

        partner_pool = self.pool.get('res.partner')        
        picking_pool = self.pool.get('stock.picking')
        ddt_pool = self.pool.get('stock.ddt')
        invoice_pool = self.pool.get('account.invoice')
        account_pool = self.pool.get('account.analytic.account')
        intervent_pool = self.pool.get('hr.analytic.timesheet')

        partner_set = set()
        contact_set = set()

        # ---------------------------------------------------------------------
        # A. Picking partner:
        # ---------------------------------------------------------------------
        domain = [
            ('min_date', '>=', '%s 00:00:00' % from_date),
            ('min_date', '<=', '%s 23:59:59' % to_date),
            ('ddt_id', '=', False), # Not DDT
            ('pick_move', '=', 'out'), # Only out movement
            ]
        picking_ids = picking_pool.search(cr, uid, domain, context=context)
        picking_proxy = picking_pool.browse(
            cr, uid, picking_ids, context=context)
        
        # Partner:
        picking_partner_ids = [item.partner_id.id for item in picking_proxy]
        partner_set.update(set(tuple(picking_partner_ids)))
        
        # Contact:
        picking_contact_ids = [item.contact_id.id for item in picking_proxy]
        contact_set.update(set(tuple(picking_contact_ids)))
    
        # ---------------------------------------------------------------------
        # B. DDT:
        # ---------------------------------------------------------------------
        domain = [
            ('delivery_date', '>=', '%s 00:00:00' % from_date),
            ('delivery_date', '<=', '%s 23:59:59' % to_date),
            ('is_invoiced', '=', False),
            #('invoice_id', '=', False), # Not Invoiced
            ]
        
        ddt_ids = ddt_pool.search(cr, uid, domain, context=context)
        ddt_proxy = ddt_pool.browse(cr, uid, ddt_ids, context=context)
        
        # Partner:
        ddt_partner_ids = [item.partner_id.id for item in ddt_proxy]
        partner_set.update(set(tuple(ddt_partner_ids)))

        # Contact:
        ddt_contact_ids = [item.contact_id.id for item in ddt_proxy]
        contact_set.update(set(tuple(ddt_contact_ids)))

        # ---------------------------------------------------------------------
        # C. Invoice:
        # ---------------------------------------------------------------------
        '''
        domain = [
            ('date_invoice', '>=', from_date),
            ('date_invoice', '<=', to_date),
            ]
        invoice_ids = invoice_pool.search(cr, uid, domain, context=context)
        invoice_partner_ids = [item.partner_id.id for item in \
            invoice_pool.browse(
                cr, uid, invoice_ids, context=context)]
        partner_set.update(set(tuple(invoice_partner_ids)))
        '''

        # ---------------------------------------------------------------------
        # D. Intervent:
        # ---------------------------------------------------------------------
        domain = [
            ('date_start', '>=', from_date),
            ('date_start', '<=', to_date),
            #('account_id.is_extra_report', '=', False),
            ]

        # Manage filter on invoiced intervent:    
        if intervent_mode == 'invoiced':
            domain.append(('is_invoiced', '=', True))    
        elif intervent_mode == 'pending':
            domain.append(('is_invoiced', '=', False))    
        # else all    
            
        intervent_ids = intervent_pool.search(cr, uid, domain, context=context)
        intervent_proxy = intervent_pool.browse(
                cr, uid, intervent_ids, context=context)
        
        # Partner
        intervent_partner_ids = [item.intervent_partner_id.id for item in \
            intervent_proxy]
        partner_set.update(set(tuple(intervent_partner_ids)))

        # Contact
        intervent_contact_ids = [item.intervent_contact_id.id for item in \
            intervent_proxy]
        contact_set.update(set(tuple(intervent_contact_ids)))
        

        # ---------------------------------------------------------------------
        #                         Excel report:
        # ---------------------------------------------------------------------
        # Partner:
        ws_name = 'Partner'
        row = 0
        header = [
            'Partner', 'Consegne', 'DDT', 
            #'Fatture', 
            'Interventi',
            ]
        width = [35, 10, 10, 10]

        excel_pool.create_worksheet(ws_name)

        # Load formats:
        f_title = excel_pool.get_format('title')
        f_header = excel_pool.get_format('header')
        f_text = excel_pool.get_format('text')
        f_number = excel_pool.get_format('number')

        # Setup columns
        excel_pool.column_width(ws_name, width)
            
        # Print header
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=f_header)
        row += 1    
        
        partner_ids = tuple(partner_set)
        for partner in sorted(partner_pool.browse(
                cr, uid, partner_ids, context=context),
                key = lambda p: p.name,
                ):

            partner_id = partner.id
            data = [
                partner.name,
                partner_id in picking_partner_ids,
                partner_id in ddt_partner_ids,
                #partner_id in invoice_partner_ids,
                partner_id in intervent_partner_ids,
                ]
            
            excel_pool.write_xls_line(
                ws_name, row, data,
                default_format=f_text
                )
            row += 1

        ws_name = 'Contatti'
        row = 0
        header = [
            'Contatti', 'Consegne', 'DDT', 
            #'Fatture', 
            'Interventi',
            ]
        width = [35, 10, 10, 10]

        excel_pool.create_worksheet(ws_name)

        # Setup columns
        excel_pool.column_width(ws_name, width)
            
        # Print header
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=f_header)
        row += 1    
        
        contact_ids = tuple(contact_set)
        for contact in sorted(partner_pool.browse(
                cr, uid, contact_ids, context=context),
                key = lambda p: p.name,
                ):

            contact_id = contact.id
            data = [
                contact.name,
                contact_id in picking_contact_ids,
                contact_id in ddt_contact_ids,
                #partner_id in invoice_partner_ids,
                contact_id in intervent_contact_ids,
                ]
            
            excel_pool.write_xls_line(
                ws_name, row, data,
                default_format=f_text
                )
            row += 1

        return excel_pool.return_attachment(
            cr, uid, 'partner_moved')

    def action_print(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        

        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        partner_id = wiz_browse.partner_id.id # Mandatory:
        contact_id = wiz_browse.contact_id.id
        account_id = wiz_browse.account_id.id
        from_date = wiz_browse.from_date
        to_date = wiz_browse.to_date
        no_account = wiz_browse.no_account
        report_mode = wiz_browse.mode

        _logger.warning('Report mode: %s' % report_mode)

        # Private report:
        activity_material_discount = wiz_browse.activity_material_discount
        activity_price = wiz_browse.activity_price #'metel_sale' 'lst_price'

        # Intervent management:
        intervent_mode = wiz_browse.intervent_mode
        mark_invoiced = wiz_browse.mark_invoiced
        
        filter_text = \
            'Interventi del periodo: [%s - %s], Cliente: %s, Contatto: %s, Commessa: %s%s' % (
                from_date or '...',
                to_date or '...',
                
                wiz_browse.partner_id.name,
                wiz_browse.contact_id.name if wiz_browse.contact_id else '/',
                
                '[%s] %s' % (
                    wiz_browse.account_id.code or '/', 
                    wiz_browse.account_id.name,  
                    ) if account_id else 'Tutte',
                ', Solo senza commessa' if no_account else '',
                )

        # Mask mode for 5 views:
        mask = {
            # Sheet: Hide bloc, Col hide, Total hide, total position
            #        Summary line mask

            'Riepilogo': [
                True, #'', # Hide block, Col Hide
                #'', 18, # Total line hide, Total position
                #'', '', 2, # Summary hide col.
                ],

            'Interventi': [
                True, '', # Hide block, Col Hide
                '', 18, # Total line hide, Total position
                '', '', 2, # Summary hide col.
                ],
            'Consegne': [
                True, '', 
                '', 12,
                '', '', 2, # Summary hide col.
                ],
            'DDT': [
                True, '', 
                '', 11,
                '', '', 2, # Summary hide col., Summary total
                ],
            #'Fatture': [True, '', '', 12],
            
            'Commesse': [
                True, '', 
                '', 12,
                '', '', 2, # Summary hide col.
                ],
            
            'Total': '',    # Mask for total
            }

        # Customer report different setup:
        if report_mode in ('detail', 'summary'):
            # -----------------------------------------------------------------
            # Hide page:
            # -----------------------------------------------------------------
            #mask['Interventi'][0] = False
            mask['DDT'][0] = False
            mask['Commesse'][0] = False
            
            # -----------------------------------------------------------------
            # Hide columns:
            # -----------------------------------------------------------------
            mask['Interventi'][1] = '011100010010000110010000'
            mask['Consegne'][1] = '000001111001001'
            mask['DDT'][1] = ''
            #mask['Fatture'][1] = ''
            #mask['Riepilogo'][1] = ''
            #mask['Commesse'][1] = ''            

            # -----------------------------------------------------------------
            # Total block:            
            # -----------------------------------------------------------------
            mask['Consegne'][2] = '001'
            mask['Consegne'][3] = 5
            
            mask['Interventi'][2] = '01'
            mask['Interventi'][3] = 7

            # -----------------------------------------------------------------
            # Summary mask
            # -----------------------------------------------------------------
            if report_mode == 'summary':
                # Summary line:
                mask['Interventi'][4] = '0001'
                mask['Consegne'][4] = '00001'
                mask['DDT'][4] = '00001'
                
                # Summary total:
                mask['Interventi'][5] = '01'
                mask['Consegne'][5] = '001'
                mask['DDT'][5] = '001'

                # Position total:
                mask['Interventi'][6] = 0
                mask['Consegne'][6] = 0
                mask['DDT'][6] = 0
            else: # detail
                # Summary line:
                mask['Interventi'][4] = '1101'
                mask['Consegne'][4] = '11001'
                mask['DDT'][4] = '11001'
            
                # Summary total:
                mask['Interventi'][5] = '01'
                mask['Consegne'][5] = '001'
                mask['DDT'][5] = '001'
                
            # -----------------------------------------------------------------
            # Total table:
            # -----------------------------------------------------------------
            mask['Total'] = '1001'

        elif report_mode == 'private':
            # Hide extra pages:
            mask['Riepilogo'][0] = False
            mask['Interventi'][0] = False
            mask['Consegne'][0] = False
            mask['DDT'][0] = False
            mask['Commesse'][0] = False
            
            
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
        mode_pool = self.pool.get('hr.intervent.user.mode')

        # ---------------------------------------------------------------------
        # Startup:
        # ---------------------------------------------------------------------
        # Load mode pricelist (to get revenue):
        mode_pricelist = {}
        mode_ids = mode_pool.search(cr, uid, [], context=context)
        for mode in mode_pool.browse(
                cr, uid, mode_ids, context=context):
            mode_pricelist[mode.id] = mode.list_price
        
        # ---------------------------------------------------------------------
        #                          COLLECT DATA:
        # ---------------------------------------------------------------------
        account_used = []

        # ---------------------------------------------------------------------
        # A. COLLECT STOCK MATERIAL:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('partner_id', '=', partner_id),
            ('min_date', '>=', '%s 00:00:00' % from_date),
            ('min_date', '<=', '%s 23:59:59' % to_date),
            ('ddt_id', '=', False), # Not DDT
            ('pick_move', '=', 'out'), # Only out movement
            ]
            
        if contact_id:
            domain.append(('contact_id', '=', contact_id))

        if no_account:
            domain.append(('account_id', '=', False))           
        elif account_id:
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
        # B. COLLECT DDT MATERIAL:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('partner_id', '=', partner_id),
            ('delivery_date', '>=', '%s 00:00:00' % from_date),
            ('delivery_date', '<=', '%s 23:59:59' % to_date),
            #('invoice_id', '=', False), # Not Invoiced
            ]

        # Not invoiced only if not internal        
        if report_mode != 'report': 
            domain.append(('is_invoiced', '=', False))

        if contact_id:
            domain.append(('contact_id', '=', contact_id))

        if no_account:
            domain.append(('account_id', '=', False))           
        elif account_id:
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
        # C. COLLECT INVOICED MATERIAL:
        # ---------------------------------------------------------------------
        """
        # Domain:
        domain = [
            ('partner_id', '=', partner_id),
            ('date_invoice', '>=', from_date),
            ('date_invoice', '<=', to_date),
            ]
        if contact_id:
            domain.append(('contact_id', '=', contact_id))

        if no_account:
            domain.append(('analytic_id', '=', False))           
        elif account_id:
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
        """

        # ---------------------------------------------------------------------
        # D. COLLECT INTERVENT:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('intervent_partner_id', '=', partner_id),
            ('date_start', '>=', from_date),
            ('date_start', '<=', to_date),
            #('account_id.is_extra_report', '=', False),
            ]
        if contact_id:
            domain.append(('intervent_contact_id', '=', contact_id))

        if no_account:
            domain.append(('account_id', '=', False))           
        elif account_id:
            domain.append(('account_id', '=', account_id))

        # Manage filter on invoiced intervent:    
        if intervent_mode == 'invoiced':
            domain.append(('is_invoiced', '=', True))    
        elif intervent_mode == 'pending':
            domain.append(('is_invoiced', '=', False))
        # TODO summary, detail

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

        if mark_invoiced and intervent_ids:
            intervent_pool.write(cr, uid, intervent_ids, {
                'is_invoiced': True,
                }, context=context)
            _logger.warning('Update as invoices %s intervent' % len(
                intervent_ids))

        # ---------------------------------------------------------------------
        # E. COLLECT ACCOUNT:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('partner_id', '=', partner_id),
            ]
        # XXX Note: Contacts dont' have account!
    
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
                'row': 1,
                'header': [],
                'width': [40, 25, 15, 15, 15],
                'data': True, # Create sheet
                },

            # -----------------------------------------------------------------
            # Sheet detail:
            # -----------------------------------------------------------------
            'Interventi': { # Invertent list
                'row': 0,
                'header': self.data_mask_filter([
                    'Commessa', 'Contatto', 'Data', 'Intervento', 'Oggetto', 
                    'Modo', 'Operazione', 
                    'Utente', 'Durata', 'Indicate', 'Totale ore', 
                    'Viaggio', 'H. Viaggio', 'Pausa', 'H. Pausa',  
                    'Richiesta', 'Intervento', 'Note',
                    'Costo', 'Prezzo totale', 'Conteggio', 'Non usare', 
                    'Stato',
                    'Fatt.',                                 
                    ], mask['Interventi'][1]),
                'width': self.data_mask_filter([
                    35, 20, 15, 15, 20, 15, 20,
                    20, 10, 10, 10, 
                    3, 10, 3, 10,
                    30, 30, 30, 
                    10, 10, 10, 5, 15, 5,
                    ], mask['Interventi'][1]),
                'total': {},
                'cost': {},
                'data': intervent_db,
                },   

            'Consegne': { # Picking to delivery
                'row': 0,
                'header': self.data_mask_filter([
                    'Commessa', 'Contatto', 'Picking', 'Data', 'Stato', 
                    'Codice', 'Descrizione', 'UM', 
                    'Q.', 'Costo ultimo', 'Scontato', 'Prezzo unitario', 
                    'Sub. ultimo', 'Sub. scontato', 'Totale',
                    ], mask['Consegne'][1]),
                'width': self.data_mask_filter([
                    35, 20, 15, 25, 20, 
                    20, 35, 15,
                    10, 10, 10, 10, 
                    15, 15, 15, ], mask['Consegne'][1]),
                'total': {},
                'data': picking_db, 
                },   

            'DDT': { # DDT not invoiced
                'row': 0,
                'header': [
                    'Commessa', 'Contatto', 'DDT', 'Data', 'Codice', 
                    'Descrizione', 'UM', 
                    'Q.', 'Costo ultimo', 'Scontato', 'METEL', 
                    'Sub. ultimo', 'Sub. scontato', 'Sub. METEL',
                    ],
                'width': [
                    35, 20, 15, 20, 25, 35, 10, 
                    15, 15, 15, 15,
                    20, 20, 20,
                    ],
                'total': {},
                'data': ddt_db, 
                },

            #'Fatture': { # Invoiced document
            #    'row': 0,
            #    'header': [
            #        'Commessa', 'Fattura', 'Data', 'Posizione', 'Articolo', 
            #        'UM', 'Q.', 'Prezzo', 'Sconto', 'Subtotale', 
            #        #'Costo',
            #        ],
            #    'width': [35, 15, 15, 20, 20, 10, 10, 10, 10, 15, ],
            #    'total': {},
            #    'cost': {},
            #    'data': invoice_db, 
            #    },

            'Commesse': { # Account
                'row': 0,
                'header': ['Fatturazione', 'Codice', 'Commessa', 'Padre', 
                    'Data', 'Posizione fiscale', 'Ore', 'Stato'],
                'width': [25, 10, 30, 20, 15, 20, 10, 10],
                'total': {},
                'data': account_db, 
                },                
            }

        summary = {
            'Interventi': {
                'header': ['Commessa', 'Intervento', 'Costo', 'Totale'],
                'data': {},
                'total_cost': 0.0, 
                #'total_discount': 0.0, 
                'total_revenue': 0.0,
                },

            'Consegne': {
                'header': ['Commessa', 'Picking', 'Costo', 'Scontato', 
                    'Totale'],
                'data': {},
                'total_cost': 0.0, 
                'total_discount': 0.0, 
                'total_revenue': 0.0, 
                },

            'DDT': {
                'header': ['Commessa', 'DDT', 'Costo', 'Scontato', 
                    'Totale'],
                'data': {},
                'total_cost': 0.0, 
                'total_discount': 0.0, 
                'total_revenue': 0.0, 
                },

            #'Fatture': {
            #    'header': ['Commessa', 'Fattura', 'Costo', 'Scontato', 
            #        'Totale'],
            #    'data': {},
            #    'total_cost': 0.0, 
            #    'total_discount': 0.0, 
            #    'total_revenue': 0.0, 
            #    },

            'Commesse': {
                'header': ['Commessa', 'Cliente'],
                'data': {},
                'total_cost': 0.0, 
                #'total_discount': 0.0, 
                'total_revenue': 0.0, 
                },                
            }

        sheet_order = [
            'Riepilogo', 
            'Interventi', 
            'Consegne', 
            'DDT', 
            #'Fatture', 
            'Commesse',
            ]

        # -------------------------------------------------------------
        # Format list:
        # -------------------------------------------------------------
        load_format = True
        for ws_name in sheet_order:
            # Check if sheet must be created:
            if ws_name in mask and not mask[ws_name][0]:
                continue

            sheet = sheets[ws_name]
            
            #if not sheet['data']:
            #    continue # No sheet creation

            # Create sheet:
            excel_pool.create_worksheet(ws_name)

            # Load formats:
            if load_format:
                f_number = excel_pool.get_format('number')
                f_number_red = excel_pool.get_format('bg_red_number')
                
                f_title = excel_pool.get_format('title')
                f_header = excel_pool.get_format('header')
                
                f_text = excel_pool.get_format('text')
                f_text_red = excel_pool.get_format('bg_red')
                load_format = False # once!

            # Setup columns
            excel_pool.column_width(ws_name, sheet['width'])
            
            # Print header
            excel_pool.write_xls_line(
                ws_name, sheet['row'], sheet['header'], 
                default_format=f_header
                )
            sheet['row'] += 1    

        # ---------------------------------------------------------------------
        # A. STOCK MATERIAL:
        # ---------------------------------------------------------------------
        if mask['Consegne'][0]:
            ws_name = 'Consegne'
            sheet = sheets[ws_name]
            summary_data = summary[ws_name]['data']

            total = sheet['total']
            for key in picking_db:  
                for picking in picking_db[key]:
                    #document_total = 0.0
                    account = picking.account_id
                    account_id = account.id
                    if account not in account_used:
                        account_used.append(account)

                    if account_id not in total:
                        total[account_id] = 0.0
                    
                    pick_total1 = 0.0
                    pick_total2 = 0.0    
                    pick_total3 = 0.0    
                    pick_error = False
                    if picking.move_lines:
                        if picking.move_lines:
                            for move in picking.move_lines:
                                product = move.product_id
                                
                                #metel_list_price:
                                standard_price = product.standard_price 
                                discount_price = product.metel_sale
                                list_price = product.lst_price
                                #list_price = move.price_unit
                                
                                subtotal1 = standard_price * move.product_qty
                                subtotal2 = discount_price * move.product_qty
                                subtotal3 = list_price * move.product_qty
                                
                                pick_total1 += subtotal1
                                pick_total2 += subtotal2
                                pick_total3 += subtotal3
                                
                                if not subtotal1 or not subtotal3:
                                    f_number_color = f_number_red
                                    f_text_color = f_text_red
                                    pick_error = True
                                else:    
                                    f_number_color = f_number
                                    f_text_color = f_text
                                    
                                data = self.data_mask_filter([  
                                    # Header
                                    picking.account_id.name or 'NON ASSEGNATA',
                                    picking.contact_id.name or '/',
                                    picking.name,
                                    picking.min_date,
                                    picking.pick_state,
                                    
                                    # Move:
                                    move.product_id.default_code,
                                    move.product_id.name,
                                    move.product_uom.name,
                                    (move.product_qty, f_number_color),
                                    
                                    # Unit price:
                                    (standard_price, f_number_color),
                                    (discount_price, f_number_color),
                                    (list_price, f_number_color),
                                    
                                    # Total price:
                                    (subtotal1, f_number_color),
                                    (subtotal2, f_number_color),
                                    (subtotal3, f_number_color),
                                    ], mask['Consegne'][1])

                                excel_pool.write_xls_line(
                                    ws_name, sheet['row'], data,
                                    default_format=f_text_color
                                    )
                                sheet['row'] += 1

                                # ---------------------------------------------
                                #                    TOTALS:
                                # ---------------------------------------------
                                # A. Total per account:                            
                                #document_total += subtotal3
                                total[account_id] += subtotal3

                                # B. Line total in same sheet:
                                summary[ws_name]['total_cost'] += subtotal1
                                summary[ws_name]['total_discount'] += subtotal2
                                summary[ws_name]['total_revenue'] += subtotal3
                                

                        else: # Picking no movements:
                            data = self.data_mask_filter([
                                # Header
                                picking.account_id.name or 'NON ASSEGNATA',
                                picking.contact_id.name or '/',
                                picking.name,
                                picking.min_date,
                                picking.pick_state,
                                
                                # Move:
                                'NESSUN MOVIMENTO',
                                '/',
                                '/',
                                (0.0, f_number),

                                (0.0, f_number),
                                (0.0, f_number),
                                (0.0, f_number),
                                
                                (0.0, f_number),
                                (0.0, f_number),
                                (0.0, f_number),
                                ], mask['Consegne'][1])
                            
                            excel_pool.write_xls_line(
                                ws_name, sheet['row'], data,
                                default_format=f_text
                                )
                            sheet['row'] += 1
                            
                    # Summary data (picking):         
                    block_key = (picking.pick_state, account)
                    if block_key not in summary_data:
                        summary_data[block_key] = []
                        
                    # Summary color:    
                    if pick_error:    
                        f_number_color = f_number_red
                        f_text_color = f_text_red
                    else:    
                        f_number_color = f_number
                        f_text_color = f_text
                        
                    summary_data[block_key].append((
                        (account.name, f_text_color), 
                        (picking.name, f_text_color), 
                        
                        (pick_total1, f_number_color),
                        (pick_total2, f_number_color),
                        (pick_total3, f_number_color),
                        )) 

                # -------------------------------------------------------------
                # Total line at the end of the block:
                # -------------------------------------------------------------
                excel_pool.write_xls_line(
                    ws_name, 
                    sheet['row'], 
                    self.data_mask_filter([
                        (summary[ws_name]['total_cost'], f_number),
                        (summary[ws_name]['total_discount'], f_number),
                        (summary[ws_name]['total_revenue'], f_number),                    
                        ], mask['Consegne'][2]), 
                    default_format=f_text, 
                    col=mask['Consegne'][3])
                        
        # ---------------------------------------------------------------------
        # B. DDT MATERIAL:
        # ---------------------------------------------------------------------
        if mask['DDT'][0]:
            ws_name = 'DDT'
            sheet = sheets[ws_name]
            summary_data = summary[ws_name]['data']

            total = sheet['total']
            for key in ddt_db:        
                for ddt in ddt_db[key]:
                    ddt_total1 = 0.0
                    ddt_total2 = 0.0
                    ddt_total3 = 0.0
                    ddt_error = False

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
                                    product = move.product_id
                                    
                                    #metel_list_price:
                                    standard_price = product.standard_price 
                                    discount_price = product.metel_sale
                                    list_price = product.lst_price
                                    #list_price = move.price_unit
                                    
                                    subtotal1 = \
                                        standard_price * move.product_qty
                                    subtotal2 = \
                                        discount_price * move.product_qty
                                    subtotal3 = \
                                        list_price * move.product_qty
                                    
                                    ddt_total1 += subtotal1
                                    ddt_total2 += subtotal2
                                    ddt_total3 += subtotal3
                                    
                                    if not subtotal1 or not subtotal3:
                                        f_number_color = f_number_red
                                        f_text_color = f_text_red
                                        ddt_error = True
                                    else:    
                                        f_number_color = f_number
                                        f_text_color = f_text
                                    
                                    data = self.data_mask_filter([  
                                        # Header
                                        ddt.account_id.name,
                                        ddt.contact_id.name or '/',
                                        ddt.name,
                                        ddt.delivery_date,
                                        
                                        # Move:
                                        product.default_code,
                                        product.name,
                                        move.product_uom.name,
                                        (move.product_qty, f_number_color),

                                        # Unit price:
                                        (standard_price, f_number_color),
                                        (discount_price, f_number_color),
                                        (list_price, f_number_color),
                                        
                                        # Total price:
                                        (subtotal1, f_number_color),
                                        (subtotal2, f_number_color),
                                        (subtotal3, f_number_color),
                                        ], mask['DDT'][1])

                                    excel_pool.write_xls_line(
                                        ws_name, sheet['row'], data,
                                        default_format=f_text_color,
                                        )
                                    sheet['row'] += 1

                                    # -----------------------------------------
                                    #                    TOTALS:
                                    # -----------------------------------------
                                    # A. Total per account:    
                                    total[account_id] += subtotal3 # XXX
                                    
                                    # B. Line total in same sheet:
                                    summary[ws_name][
                                        'total_cost'] += subtotal1
                                    summary[ws_name][
                                        'total_discount'] += subtotal2
                                    summary[ws_name][
                                        'total_revenue'] += subtotal3


                            else: # Picking no movements:
                                data = self.data_mask_filter([
                                    # Header
                                    ddt.account_id.name or 'NON ASSEGNATA',
                                    ddt.contact_id.name or '/',
                                    ddt.name,
                                    ddt.delivery_date,
                                    
                                    # Move:
                                    'NESSUN MOVIMENTO',
                                    '/',
                                    (0.0, f_number),
                                    (0.0, f_number),
                                    (0.0, f_number),
                                    ], mask['DDT'][1])
                                
                                excel_pool.write_xls_line(
                                    ws_name, sheet['row'], data,
                                    default_format=f_text
                                    )
                                sheet['row'] += 1
                    else: # no 
                        data = self.data_mask_filter([
                            # Header
                            ddt.account_id.name or 'NON ASSEGNATA',
                            ddt.contact_id.name or '/',
                            ddt.name,
                            ddt.delivery_date,
                            
                            # Move:
                            'NESSUN PICKING',
                            '/',
                            (0.0, f_number),
                            (0.0, f_number),
                            (0.0, f_number),
                            ], mask['DDT'][1])
                        
                        excel_pool.write_xls_line(
                            ws_name, sheet['row'], data,
                            default_format=f_text
                            )
                        sheet['row'] += 1

                    # Summary data (picking):         
                    block_key = (account.name, ddt.name)
                    if block_key not in summary_data:
                        summary_data[block_key] = []
                        
                    # Summary color:    
                    if ddt_error:    
                        f_number_color = f_number_red
                        f_text_color = f_text_red
                    else:    
                        f_number_color = f_number
                        f_text_color = f_text
                        
                    summary_data[block_key].append((
                        (account.name, f_text_color), 
                        (ddt.name, f_text_color), 
                        
                        (ddt_total1, f_number_color),
                        (ddt_total2, f_number_color),
                        (ddt_total3, f_number_color),
                        )) 

            # -----------------------------------------------------------------
            # Total line at the end of the block:
            # -----------------------------------------------------------------
            excel_pool.write_xls_line(
                ws_name, 
                sheet['row'], 
                self.data_mask_filter([
                    (summary[ws_name]['total_cost'], f_number),
                    (summary[ws_name]['total_discount'], f_number),
                    (summary[ws_name]['total_revenue'], f_number),
                    ], mask['DDT'][2]), 
                default_format=f_text, col=mask['DDT'][3])

        # ---------------------------------------------------------------------
        # C. INVOICED MATERIAL:
        # ---------------------------------------------------------------------
        """ws_name = 'Fatture'
        sheet = sheets[ws_name]
        summary_data = summary[ws_name]['data']

        total = sheet['total']
        cost = sheet['cost']
        for key in invoice_db:
            for invoice in invoice_db[key]:
                document_total = 0.0
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
                    
                    # Total:    
                    total[account_id] += subtotal
                    document_total += subtotal
                    
                    excel_pool.write_xls_line(
                        ws_name, sheet['row'], data,
                        default_format=f_text
                        )
                    sheet['row'] += 1

                # Summary data (Invoice):         
                block_key = (account.name, invoice.number)
                if block_key not in summary_data:
                    summary_data[block_key] = []
                summary_data[block_key].append((
                    account.name, 
                    invoice.number, 
                    (document_total, f_number),
                    (0.0, f_number), # TODO
                    )) 
        """

        # ---------------------------------------------------------------------
        # D. INTERVENT:
        # ---------------------------------------------------------------------
        if mask['Interventi'][0]: # Show / Hide page:
            ws_name = 'Interventi'
            sheet = sheets[ws_name]
            summary_data = summary[ws_name]['data']

            partner_forced = False # update first time!
            
            total = sheet['total']
            cost = sheet['cost']

            for key in intervent_db:
                for intervent in intervent_db[key]:
                    # Readability:
                    user = intervent.user_id
                    partner = intervent.intervent_partner_id
                    account = intervent.account_id
                    account_id = account.id
                    user_id = user.id
                    user_mode_id = intervent.user_mode_id.id
                    
                    # ---------------------------------------------------------
                    # Initial setup of mapping and forced price database:
                    # ---------------------------------------------------------
                    if partner_forced == False:
                        partner_forced = {}
                        for forced in partner.mode_revenue_ids:        
                            partner_forced[forced.mode_id.id] = \
                                forced.list_price
                    # ---------------------------------------------------------

                    # Read revenue:        
                    if user_mode_id in partner_forced: # partner forced
                        unit_revenue = partner_forced[user_mode_id]
                    else: # read for default list:
                        unit_revenue = mode_pricelist.get(user_mode_id, 0.0)

                    if account and account not in account_used:
                        account_used.append(account)

                    if account_id not in total:
                        total[account_id] = 0.0
                        cost[account_id] = 0.0
                    
                    #document_total = 0.0
                    this_revenue = intervent.unit_amount * unit_revenue
                    this_cost = -intervent.amount

                    if not this_revenue or not this_cost:
                        f_number_color = f_number_red
                        f_text_color = f_text_red
                        ddt_error = True
                    else:    
                        f_number_color = f_number
                        f_text_color = f_text

                    data = self.data_mask_filter([
                        account.name or 'NON ASSEGNATA',
                        intervent.intervent_contact_id.name or '/',
                        intervent.date_start,
                        intervent.ref or 'BOZZA',
                        intervent.name,
                        intervent.mode,
                        intervent.operation_id.name or '',
                        intervent.user_id.name,
                        
                        # Intervent:
                        intervent.intervent_duration,
                        intervent.intervent_total,
                        intervent.unit_amount,

                        # Extra hour:                    
                        intervent.trip_require,
                        intervent.trip_hour,                    
                        intervent.break_require,
                        intervent.break_hour,
                        
                        # Text:
                        intervent.intervention_request,
                        intervent.intervention or intervent.name,
                        intervent.internal_note,
                        
                        # Revenue:
                        (this_cost, f_number_color), # total cost
                        (this_revenue, f_number_color), # total revenue
                        
                        intervent.to_invoice.name or '/',
                        'X' if intervent.not_in_report else '',
                        
                        intervent.state,
                        'X' if intervent.is_invoiced else '',
                        ], mask['Interventi'][1])

                    excel_pool.write_xls_line(
                        ws_name, sheet['row'], data,
                        default_format=f_text_color
                        )
                    sheet['row'] += 1

                    # Summary data (Intervent):   
                    block_key = (account.name, intervent.ref)
                    if block_key not in summary_data:
                        summary_data[block_key] = []
                    summary_data[block_key].append((
                        (account.name, f_text_color), 
                        (intervent.ref, f_text_color), 

                        (this_cost, f_number_color),                    
                        (this_revenue, f_number_color),
                        ))

                    # ---------------------------------------------------------
                    # Totals:
                    # ---------------------------------------------------------
                    # A. Total per account:                            
                    cost[account_id] += this_cost
                    total[account_id] += this_revenue
                    
                    # B. Line total in same sheet:
                    summary[ws_name]['total_cost'] += this_cost
                    summary[ws_name]['total_revenue'] += this_revenue

                # -------------------------------------------------------------
                # Total line at the end of the block:
                # -------------------------------------------------------------
                excel_pool.write_xls_line(
                    ws_name, 
                    sheet['row'], 
                    self.data_mask_filter([
                        (summary[ws_name]['total_cost'], f_number),
                        (summary[ws_name]['total_revenue'], f_number),
                        ], mask['Interventi'][2]), 
                    default_format=f_text, 
                    col=mask['Interventi'][3])

        # ---------------------------------------------------------------------
        # E. ACCOUNT:
        # ---------------------------------------------------------------------
        if mask['Commesse'][0]:
            ws_name = 'Commesse'
            sheet = sheets[ws_name]
            summary_data = summary[ws_name]['data']

            # Block all account:
            for key in account_db:
                for account in account_db[key]:
                    data = self.data_mask_filter([
                        account.account_mode,
                        account.code,
                        account.name,
                        account.parent_id.name or '/',
                        account.from_date,
                        '/', #account.fiscal_position.name,
                        account.total_hours,
                        account.state,
                        ], mask['Commesse'][1])
                    
                    excel_pool.write_xls_line(
                        ws_name, sheet['row'], data,
                        default_format=f_text
                        )
                    sheet['row'] += 1

            
            # Block account used:
            sheet['row'] += 2
            excel_pool.write_xls_line(
                ws_name, sheet['row'], [u'Commesse toccate nel periodo:', ],
                default_format=f_title
                )

            sheet['row'] += 1
            excel_pool.write_xls_line(
                ws_name, sheet['row'], sheet['header'],
                default_format=f_header
                )

            sheet['row'] += 1
            for account in account_used:   
                if not account:
                    continue
                data = self.data_mask_filter([
                    account.account_mode,
                    account.code,
                    account.name,
                    account.parent_id.name or '/',
                    account.from_date,
                    '/', #account.fiscal_position.name,
                    account.total_hours,
                    account.state,
                    ], mask['Commesse'][1])
                
                excel_pool.write_xls_line(
                    ws_name, sheet['row'], data,
                    default_format=f_text
                    )
                sheet['row'] += 1

        # ---------------------------------------------------------------------
        # SUMMARY:
        # ---------------------------------------------------------------------
        if mask['Riepilogo'][0]:
            ws_name = 'Riepilogo'
            sheet = sheets[ws_name]

            # Filter text:
            excel_pool.write_xls_line(ws_name, 0, [
                filter_text,
                ],default_format=f_title)
            
            for block in sheet_order[1:-1]: # Jump TODO commesse?!?
                # Check if sheet must be created:
                if block in mask and not mask[block][0]:
                    continue

                block_record = summary[block]

                excel_pool.write_xls_line(
                    ws_name, sheet['row'], ['Blocco: %s' % block],
                    default_format=f_title
                    )
                sheet['row'] += 1

                excel_pool.write_xls_line(
                    ws_name, 
                    sheet['row'], 
                    self.data_mask_filter(
                        block_record['header'], mask[block][4]),
                    default_format=f_header
                    )
                sheet['row'] += 1
                
                for key in block_record['data']:
                    if report_mode != 'summary':
                        for record in block_record['data'][key]: 
                            excel_pool.write_xls_line(
                                ws_name, 
                                sheet['row'], 
                                self.data_mask_filter(record, mask[block][4]),
                                default_format=f_text,
                                )
                            sheet['row'] += 1

                # -------------------------------------------------------------                 
                # Total line:        
                # -------------------------------------------------------------                  
                if 'total_discount' in summary[block]:
                    data = self.data_mask_filter([
                        (summary[block]['total_cost'], f_number),
                        (summary[block]['total_discount'], f_number),
                        (summary[block]['total_revenue'], f_number),
                        ], mask[block][5])
                else:        
                    data = self.data_mask_filter([
                        (summary[block]['total_cost'], f_number),
                        (summary[block]['total_revenue'], f_number),
                        ], mask[block][5])

                excel_pool.write_xls_line(
                    ws_name, sheet['row'], data, default_format=f_text, 
                    col=mask[block][6])

                sheet['row'] += 1
        
            # -----------------------------------------------------------------
            # TOTAL BLOCK:
            # -----------------------------------------------------------------
            # Header:
            sheet['row'] += 1
            excel_pool.write_xls_line(
                ws_name, sheet['row'], self.data_mask_filter([
                    'Blocco',
                    'Costo', 
                    'Scontato', 
                    'Listino',
                    ], mask['Total']), default_format=f_header)
            total = {
                'total_cost': 0.0,
                'total_discount': 0.0,
                'total_revenue': 0.0,
                }

            for block in sheet_order[1:]:

                # -------------------------------------------------------------
                # Parameters:
                # -------------------------------------------------------------
                total_cost = summary[block].get('total_cost', 0.0)
                total_discount = summary[block].get('total_discount', 0.0)
                total_revenue = summary[block].get('total_revenue', 0.0)
                
                if not any((total_cost, total_discount, total_revenue)):
                    continue

                sheet['row'] += 1
                excel_pool.write_xls_line(
                    ws_name, sheet['row'], 
                    self.data_mask_filter([ 
                        block, 
                        (total_cost, f_number),
                        (total_discount, f_number),
                        (total_revenue, f_number),
                        ], mask['Total']), default_format=f_text)

                # -------------------------------------------------------------
                # Total  
                # -------------------------------------------------------------
                total['total_cost'] += total_cost
                total['total_discount'] += total_discount
                total['total_revenue'] += total_revenue

            # Final total of the table:
            sheet['row'] += 1
            excel_pool.write_xls_line(
                ws_name, sheet['row'], self.data_mask_filter([
                ('Totale:', f_title),
                (total.get('total_cost', 0.0), f_number),
                (total.get('total_discount', 0.0), f_number),
                (total.get('total_revenue', 0.0), f_number),
                ], mask['Total']), default_format=f_text)            

        # ---------------------------------------------------------------------
        # PRIVATE MODE:
        # ---------------------------------------------------------------------
        if report_mode == 'private':
            ws_name = 'Ridotta'
            excel_pool.create_worksheet(ws_name)

            partner = wiz_browse.partner_id # For information
            company = partner.company_id
            
            row = 0

            f_number = excel_pool.get_format('number')
            f_number_red = excel_pool.get_format('bg_red_number')
            
            f_title = excel_pool.get_format('title')
            f_header = excel_pool.get_format('header')
            
            f_text = excel_pool.get_format('text')
            f_text_red = excel_pool.get_format('bg_red')

            # Setup columns
            excel_pool.column_width(ws_name, [20, 30, 10, 20, 15, 15])

            # -----------------------------------------------------------------
            # Insert Logo:
            logo_field = company.logo or company.partner_id.image
            data_image = excel_pool.clean_odoo_binary(logo_field)

            excel_pool.row_height(ws_name, (row, ), height=105)
            excel_pool.write_image(ws_name, row, 0, 
                x_offset=0, y_offset=0, 
                x_scale=0.5, y_scale=0.5, 
                positioning=2,
                filename=False, 
                data=data_image, 
                tip='Logo',
                #url=False, 
                )
            excel_pool.write_xls_line(ws_name, row, [
                '', '',
                '%s\nIndirizzo: %s %s %s\nE-mail: %s\nTelefono: %s' % (
                    company.name,
                    company.street or '',
                    company.zip or '',
                    company.city or '',
                    company.email or '',
                    company.phone or '',
                    ),
                ], default_format=f_title)
                        
            row += 2
            # Partner information:
            excel_pool.write_xls_line(ws_name, row, [
                ('Cliente', f_title),
                partner.name,
                ], default_format=f_title)
            row += 1             
            excel_pool.write_xls_line(ws_name, row, [
                ('Indirizzo', f_title),
                'Via %s - %s %s' % (
                    partner.street or '',
                    partner.zip or '',
                    partner.city or '',
                    )
                ],default_format=f_title)

            row += 2
            # Filter text:
            excel_pool.write_xls_line(ws_name, row, [
                filter_text,
                ],default_format=f_title)

            private_summary = []
            # -----------------------------------------------------------------
            # A. STOCK MATERIAL:
            # -----------------------------------------------------------------
            # Print header
            row += 2
            excel_pool.write_xls_line(
                ws_name, row, [
                    'MATERIALI', '', '', '', '', '',
                    ], default_format=f_header)

            row += 1
            excel_pool.write_xls_line(
                ws_name, row, [
                    'Codice', 'Descrizione', 'UM', 'Q.', 'Prezzo unitario', 
                    'Totale',
                    ], default_format=f_header)

            total = 0.0
            for key in picking_db:  
                for picking in picking_db[key]:
                    if picking.move_lines:
                        for move in picking.move_lines:
                            product = move.product_id
                            
                            #metel_list_price:
                            #standard_price = product.standard_price 
                            #discount_price = product.metel_sale
                            #list_price = product.lst_price
                            #list_price = move.price_unit

                            if activity_price == 'lst_price':
                                price = product.lst_price
                            else:    
                                price = product.metel_sale
                            subtotal = price * move.product_qty                            
                            
                            if subtotal:
                                f_number_color = f_number
                                f_text_color = f_text
                            else:    
                                f_number_color = f_number_red
                                f_text_color = f_text_red
                                pick_error = True
                                
                            data = [
                                move.product_id.default_code,
                                move.product_id.name,
                                move.product_uom.name,
                                (move.product_qty, f_number_color),
                                
                                (price, f_number_color),
                                (subtotal, f_number_color),
                                ]
                            row += 1
                            excel_pool.write_xls_line(
                                ws_name, row, data,
                                default_format=f_text_color
                                )

                            # ---------------------------------------------
                            #                    TOTALS:
                            # ---------------------------------------------
                            total += subtotal

                # -------------------------------------------------------------
                # Total line at the end of the block:
                # -------------------------------------------------------------
                row += 1 
                excel_pool.write_xls_line(
                    ws_name, row, [(total, f_number)], default_format=f_text, 
                    col=5)
                    
                # Discount if present:
                if activity_material_discount:
                    row += 1 
                    discount = total * (
                        100.0 - activity_material_discount) / 100.0
                    excel_pool.write_xls_line(
                        ws_name, row, [
                            '- %s%% Sconto' % activity_material_discount,
                            (discount, f_number),
                            ], default_format=f_text, 
                        col=4)
                    private_summary.append(('Consegne', discount))
                else:
                    private_summary.append(('Consegne', total))

            # -----------------------------------------------------------------
            # B. DDT MATERIAL:
            # -----------------------------------------------------------------
            # Print header
            row += 2
            excel_pool.write_xls_line(
                ws_name, row, [
                    'MATERIALI DDT', '', '', '', '', '',
                    ], default_format=f_header)

            row += 1
            excel_pool.write_xls_line(
                ws_name, row, [
                    'Codice', 'Descrizione', 'UM', 'Q.', 'Prezzo unitario', 
                    'Totale',
                    ], default_format=f_header)

            total = 0.0
            for key in ddt_db:        
                for ddt in ddt_db[key]:
                    if ddt.picking_ids:
                        for picking in ddt.picking_ids:
                            for move in picking.move_lines:
                                product = move.product_id
                                
                                #metel_list_price:
                                #standard_price = product.standard_price 
                                #discount_price = product.metel_sale
                                #list_price = product.lst_price
                                #list_price = move.price_unit

                                if activity_price == 'lst_price':
                                    price = product.lst_price
                                else:    
                                    price = product.metel_sale
                                subtotal = price * move.product_qty                            
                                
                                if subtotal:
                                    f_number_color = f_number
                                    f_text_color = f_text
                                else:    
                                    f_number_color = f_number_red
                                    f_text_color = f_text_red
                                    ddt_error = True
                                
                                data = [  
                                    product.default_code,
                                    product.name,
                                    move.product_uom.name,
                                    (move.product_qty, f_number_color),

                                    (price, f_number_color),
                                    (subtotal, f_number_color),
                                    ]

                                row += 1
                                excel_pool.write_xls_line(
                                    ws_name, row, data,
                                    default_format=f_text_color,
                                    )

                                # -----------------------------------------
                                #                    TOTALS:
                                # -----------------------------------------
                                total += subtotal
                        
            # -------------------------------------------------------------
            # Total line at the end of the block:
            # -------------------------------------------------------------
            row += 1 
            excel_pool.write_xls_line(
                ws_name, row, [(total, f_number)], default_format=f_text, 
                col=5)

            # Discount if present:
            if activity_material_discount:
                row += 1 
                discount = total * (
                    100.0 - activity_material_discount) / 100.0
                excel_pool.write_xls_line(
                    ws_name, row, [
                        '- %s%% Sconto' % activity_material_discount,
                        (discount, f_number),
                        ], default_format=f_text, 
                    col=4)
                private_summary.append(('DDT', discount))
            else:
                private_summary.append(('DDT', total))

            # -----------------------------------------------------------------
            # C. INTERVENT:
            # -----------------------------------------------------------------
            partner_forced = False # update first time!        
            total = 0.0

            # Print header
            row += 2
            excel_pool.write_xls_line(
                ws_name, row, [
                    'MANODOPERA', '', '', '', '', 
                    ], default_format=f_header)

            row += 1
            excel_pool.write_xls_line(
                ws_name, row, [
                    #'Codice', 'Descrizione', 'UM', 'Q.', 'Prezzo unitario', 
                    #'Totale',
                    'Data', 'Intervento', 'H.', 'Utente', 'Prezzo totale',
                    ], default_format=f_header)

            for key in intervent_db:
                for intervent in intervent_db[key]:
                    # Readability:
                    user = intervent.user_id
                    partner = intervent.intervent_partner_id
                    user_mode_id = intervent.user_mode_id.id
                    
                    # ---------------------------------------------------------
                    # Initial setup of mapping and forced price database:
                    # ---------------------------------------------------------
                    if partner_forced == False:
                        partner_forced = {}
                        for forced in partner.mode_revenue_ids:        
                            partner_forced[forced.mode_id.id] = \
                                forced.list_price
                    # ---------------------------------------------------------
                    # Read revenue:        
                    if user_mode_id in partner_forced: # partner forced
                        unit_revenue = partner_forced[user_mode_id]
                    else: # read for default list:
                        unit_revenue = mode_pricelist.get(user_mode_id, 0.0)

                    this_revenue = intervent.unit_amount * unit_revenue
                    #this_cost = -intervent.amount

                    if this_revenue:
                        f_number_color = f_number
                        f_text_color = f_text
                    else:    
                        f_number_color = f_number_red
                        f_text_color = f_text_red
                        ddt_error = True

                    data = [
                        intervent.date_start,
                        intervent.name,
                        intervent.intervent_total,
                        user.name,
                        #intervent.intervent_duration intervent.unit_amount,
                        (this_revenue, f_number_color), # total revenue
                        ]

                    row += 1
                    excel_pool.write_xls_line(
                        ws_name, row, data,
                        default_format=f_text_color
                        )
                    total += this_revenue

            # -------------------------------------------------------------
            # Total line at the end of the block:
            # -------------------------------------------------------------
            row += 1
            excel_pool.write_xls_line(
                ws_name, row, [
                    (total, f_number),
                    ], 
                default_format=f_text, col=4)
            private_summary.append(('Interventi', total))

            # -----------------------------------------------------------------
            # SUMMARY:
            # -----------------------------------------------------------------
            total = 0.0

            # Print header
            row += 2
            excel_pool.write_xls_line(
                ws_name, row, [
                    'Blocco', 'Totale',
                    ], default_format=f_header)
            
            for block, subtotal in private_summary:
                row += 1
                total += subtotal
                excel_pool.write_xls_line(
                    ws_name, row, [
                        block, 
                        (subtotal, f_number),
                        ], default_format=f_text)
            row += 1            
            excel_pool.write_xls_line(
                ws_name, row, [
                    total,
                    ], default_format=f_number, col=1)

        return excel_pool.return_attachment(cr, uid, 'partner_activity')

    _columns = {
        'mode': fields.selection([
            # Internal:
            ('partner', 'Partners list'), # List custsomer touched
            ('report', 'Partner report'), # Internal detail
            
            # Client:
            ('detail', 'Customer detail'),
            ('summary', 'Customer summary'),

            ('private', 'Private (minimal)'),
            ], 'Mode', required=True),
            
        'partner_id': fields.many2one(
            'res.partner', 'Partner'),
        'contact_id': fields.many2one(
            'res.partner', 'Contact'),

        'account_id': fields.many2one(
            'account.analytic.account', 'Account'),
        'no_account': fields.boolean('No account'),

        'from_date': fields.date('From date >= ', required=True),
        'to_date': fields.date('To date <', required=True),
        'float_time': fields.boolean('Formatted hour', 
            help='If checked print hour in HH:MM format'),
         
        # Intervent management:
        'intervent_mode': fields.selection([
            ('pending', 'Pending'),
            ('invoiced', 'Invoiced'),
            ('all', 'All'),
            ], 'Intervent mode', required=True,
            help='Select intervent depend on invoice mode'),
        'mark_invoiced': fields.boolean('Mark intervent as invoiced', 
            help='All selected intervent will be marked as invoiced'),

        # Private report:
        'activity_material_discount': fields.float(
            'Material discount (report activity)', digits=(16, 4)),
        'activity_price': fields.selection([
            ('metel_sale', 'Discount price'),
            ('lst_price', 'List price'),
            ], 'Price used (report activity'),
        }
        
    _defaults = {
        'mode': lambda *x: 'report',
        'float_time': lambda *x: True,
        'from_date': lambda *x: datetime.now().strftime('%Y-%m-01'),
        'to_date': lambda *x: (
            datetime.now() + relativedelta(months=1)).strftime('%Y-%m-01'),
        'intervent_mode': lambda *x: 'pending',
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

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

# Utility:
def formatLang(date):
    """ format date
    """
    date = (date or '').strip()
    if not date:
        return ''

    date_part = (date or '')[:10]
    hour_part = (date or '')[10:]

    italian_date = '%s/%s/%s%s' % (
        date[8:10],
        date[5:7],
        date[:4],
        hour_part,
        )
    return italian_date


class ResPartnerActivityWizard(orm.TransientModel):
    """ Wizard for partner activity
    """
    _name = 'res.partner.activity.wizard'

    def extract_user_activity(self, cr, uid, wiz_browse, context=None):
        """ Report for user activity
        """
        excel_pool = self.pool.get('excel.writer')
        intervent_pool = self.pool.get('hr.analytic.timesheet')
        mode_convert = {
            'phone': 'Telefonico',
            'passenger': 'Passeggero',
            'customer': 'Cliente',
            'connection': 'Teleassistenza',
            'company': 'Azienda',
        }

        # Extract data from wizard:
        user_id = wiz_browse.user_id.id
        from_date = wiz_browse.from_date
        to_date = wiz_browse.to_date

        # ---------------------------------------------------------------------
        # A. User activity:
        # ---------------------------------------------------------------------
        domain = [
            ('date_start', '>=', '%s 00:00:00' % from_date),
            ('date_start', '<=', '%s 23:59:59' % to_date),
            ('user_id', '=', user_id),
        ]

        # ---------------------------------------------------------------------
        # Excel create:
        # ---------------------------------------------------------------------
        ws_name = u'Attività utente'
        excel_pool.create_worksheet(ws_name)

        # Load formats:
        f_title = excel_pool.get_format('title')
        f_header = excel_pool.get_format('header')
        f_text = excel_pool.get_format('text')
        f_number = excel_pool.get_format('number')

        # Setup columns
        header = [
            'Utente',
            'Data', 'Durata',
            'Rif.', u'Modalità',
            'Partner', 'Commessa', u'Città', 'Prov.',
            'Oggetto', 'Descrizione',
        ]
        width = [
            20,
            17, 10,
            6, 10,
            45, 35, 30, 20,
            30, 80,
        ]
        excel_pool.column_width(ws_name, width)

        # Print header
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=f_header)
        excel_pool.autofilter(ws_name, row, 0, row, len(header))
        excel_pool.freeze_panes(ws_name, 1, 2)

        intervent_ids = intervent_pool.search(
            cr, uid, domain, context=context)
        intervent_proxy = intervent_pool.browse(
            cr, uid, intervent_ids, context=context)
        for intervent in sorted(intervent_proxy, key=lambda i: i.date_start):
            row += 1
            excel_pool.write_xls_line(
                ws_name, row, [
                    intervent.user_id.name or '',
                    intervent.date_start or '',
                    intervent.intervent_duration or '',
                    intervent.ref or '',
                    mode_convert.get(intervent.mode, ''),
                    intervent.intervent_partner_id.name or '',
                    intervent.account_id.name or '',
                    intervent.account_id.partner_id.city or '',
                    intervent.account_id.partner_id.state_id.name or '',
                    intervent.name or '',
                    intervent.intervention or '',
                ], default_format=f_text)
        return excel_pool.return_attachment(cr, uid, 'user_activity')

    def material_update(self, cr, uid, material_rows, move, context=None):
        """ Update total from move:
        """
        product_pool = self.pool.get('product.product')

        (product_name, list_price, standard_price,
            discount_price, discount_vat) = product_pool.extract_product_data(
                cr, uid, move, context=context)

        product = move.product_id
        # Use also key the product name, cost for XXX product
        key = (product, product_name, discount_price)

        qty = move.product_qty
        subtotal1 = standard_price * move.product_qty
        subtotal2 = discount_price * move.product_qty
        subtotal3 = list_price * move.product_qty

        if key in material_rows:
            material_rows[key][0] += qty
            material_rows[key][4] += subtotal1
            material_rows[key][5] += subtotal2
            material_rows[key][6] += subtotal3
        else:
            material_rows[key] = [
                qty,
                standard_price,
                discount_price,
                list_price,
                subtotal1,
                subtotal2,
                subtotal3,
                ]
        return True

    # -------------------------------------------------------------------------
    # Onchange:
    # -------------------------------------------------------------------------
    def onchange_partner_private(self, cr, uid, ids, partner_id, context=None):
        """ Change default discount and price for private report
        """
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
        """ data = list of data
            mask = bit list with 0 or 1
            Using mask return data with value if 1 in the mask
        """
        if not mask:
            return data
        return [data[i] for i in range(0, len(data)) if mask[i:i + 1] != '0']

    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------
    def action_print_touched(self, cr, uid, ids, context=None):
        """ List of partner touched in that period
        """
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
        product_pool = self.pool.get('product.product')

        partner_set = set()
        contact_set = set()
        account_set = set()

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

        # Account:
        picking_account_ids = [item.account_id.id for item in picking_proxy]
        account_set.update(set(tuple(picking_account_ids)))

        # ---------------------------------------------------------------------
        # B. DDT:
        # ---------------------------------------------------------------------
        # 2 search for different date value
        domain = [
            ('is_invoiced', '=', False),
            ('delivery_date', '>=', '%s 00:00:00' % from_date),
            ('delivery_date', '<=', '%s 23:59:59' % to_date),
            ]
        ddt_delivery_ids = set(
            ddt_pool.search(cr, uid, domain, context=context))

        domain = [
            ('is_invoiced', '=', False),
            ('date', '>=', '%s 00:00:00' % from_date),
            ('date', '<=', '%s 23:59:59' % to_date),
            ]
        ddt_date_ids = set(
            ddt_pool.search(cr, uid, domain, context=context))
        ddt_ids = tuple(ddt_delivery_ids | ddt_date_ids)
        _logger.warning('List Delivery: %s, Date: %s, Total: %s' % (
            len(ddt_delivery_ids),
            len(ddt_date_ids),
            len(ddt_ids),
            ))

        ddt_proxy = ddt_pool.browse(cr, uid, ddt_ids, context=context)

        # Partner:
        ddt_partner_ids = [item.partner_id.id for item in ddt_proxy]
        partner_set.update(set(tuple(ddt_partner_ids)))

        # Contact:
        ddt_contact_ids = [item.contact_id.id for item in ddt_proxy]
        contact_set.update(set(tuple(ddt_contact_ids)))

        # Account:
        ddt_account_ids = [item.account_id.id for item in ddt_proxy]
        account_set.update(set(tuple(ddt_account_ids)))

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
            # ('account_id.is_extra_report', '=', False),
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
        intervent_partner_ids = [item.intervent_partner_id.id for item in
                                 intervent_proxy]
        partner_set.update(set(tuple(intervent_partner_ids)))

        # Contact
        intervent_contact_ids = [item.intervent_contact_id.id for item in
                                 intervent_proxy]
        contact_set.update(set(tuple(intervent_contact_ids)))

        # Account:
        intervent_account_ids = [item.account_id.id for item in \
            intervent_proxy]
        account_set.update(set(tuple(intervent_account_ids)))

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
        width = [45, 10, 10, 10]

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
                key=lambda p: p.name,
                ):

            partner_id = partner.id
            data = [
                u'%s' % (partner.name or ''),
                partner_id in picking_partner_ids,
                partner_id in ddt_partner_ids,
                # partner_id in invoice_partner_ids,
                partner_id in intervent_partner_ids,
                ]

            excel_pool.write_xls_line(
                ws_name, row, data,
                default_format=f_text
                )
            row += 1

        # Partner:
        ws_name = 'Commesse'
        row = 0
        header = [
            'Partner', 'Commessa', 'Consegne', 'DDT', 'Interventi',
            # 'Fatture',
            ]
        width = [45, 40, 10, 10, 10]
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

        account_ids = tuple(account_set)
        for account in sorted(account_pool.browse(
                cr, uid, account_ids, context=context),
                key=lambda p: (
                    p.partner_id.name if p.partner_id else '', p.name),
                ):
            if not account.name:
                continue

            partner = account.partner_id
            account_id = account.id
            data = [
                u'%s' % (partner.name or ''),
                u'%s' % (account.name or ''),
                account_id in picking_account_ids,
                account_id in ddt_account_ids,
                # account_id in invoice_account_ids,
                account_id in intervent_account_ids,
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
        width = [45, 10, 10, 10]

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
                key=lambda p: p.name,
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
        """ Event for button done
        """
        if context is None:
            context = {}

        product_pool = self.pool.get('product.product')

        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        partner_id = wiz_browse.partner_id.id # Mandatory:
        contact_id = wiz_browse.contact_id.id
        account_id = wiz_browse.account_id.id
        from_date = wiz_browse.from_date
        to_date = wiz_browse.to_date
        no_account = wiz_browse.no_account
        report_mode = wiz_browse.mode
        manual_invoice_ids = wiz_browse.account_id.manual_invoice_ids

        _logger.warning('Report mode: %s' % report_mode)

        # Private report:
        activity_material_discount = wiz_browse.activity_material_discount
        activity_price = wiz_browse.activity_price  # 'metel_sale' 'lst_price'

        # Intervent management:
        intervent_mode = wiz_browse.intervent_mode
        ddt_mode = wiz_browse.ddt_mode
        mark_invoiced = wiz_browse.mark_invoiced

        partner_text = 'Cliente: %s, ' % wiz_browse.partner_id.name
        # TODO intervent_mode, ddt_mode
        filter_text = \
            'Interventi del periodo: [%s - %s], %sContatto: %s, Commessa: %s%s' % (
                formatLang(from_date) or '...',
                formatLang(to_date) or '...',

                '' if report_mode == 'private' else partner_text,
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
                True,  # '', # Hide block, Col Hide
                # '', 18, # Total line hide, Total position
                # '', '', 2, # Summary hide col.
                ],

            'Interventi': [
                True, '', # Hide block, Col Hide
                '', 18, # Total line hide, Total position
                '', '', 2,  # Summary hide col.
                ],
            'Consegne': [
                True, '',
                '', 12,
                '', '', 2,  # Summary hide col.
                ],
            'DDT': [
                True, '',
                '', 11,
                '', '111', 2,  # Summary hide col., Summary total
                ],

            'Fatture': [
                False, '',
                '001', 6,
                '', '001', 2,  # Summary hide col., Summary total
                ],

            'Spese': [
                True, '',
                '', 4,  # Total line hide, Total position
                '', '', 2,  # TODO CHECK HERE!! # Summary hide col.
                ],

            'Materiali': [
                False, '1111100100',
                # '', 11,
                # '', '', 2, # Summary hide col., Summary total
                ],

            'Commesse': [
                True, '',
                '', 12,
                '', '', 2,  # Summary hide col.
                ],

            'Total': '',  # Mask for total
            }

        # Customer report different setup:
        if report_mode == 'user':
            return self.extract_user_activity(
                cr, uid, wiz_browse, context=context)
        if report_mode in ('detail', 'summary'):
            # -----------------------------------------------------------------
            # Hide page:
            # -----------------------------------------------------------------
            # mask['Interventi'][0] = False
            mask['DDT'][0] = False
            mask['Commesse'][0] = False

            # -----------------------------------------------------------------
            # Hide columns:
            # -----------------------------------------------------------------
            mask['Interventi'][1] = '011100010010000110010000'
            mask['Consegne'][1] = '000001111001001'
            mask['DDT'][1] = ''
            # mask['Fatture'][1] = ''
            # mask['Riepilogo'][1] = ''
            # mask['Commesse'][1] = ''

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
        elif report_mode == 'report':
            mask['Materiali'][0] = True
            mask['Fatture'][0] = True
        elif report_mode == 'private':
            # Hide extra pages:
            mask['Riepilogo'][0] = False
            mask['Interventi'][0] = False
            mask['Consegne'][0] = False
            mask['DDT'][0] = False
            mask['Spese'][0] = False
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
        product_pool = self.pool.get('product.product')
        expence_pool = self.pool.get('account.analytic.expence')

        # Interventi:
        intervent_pool = self.pool.get('hr.analytic.timesheet')
        mode_pool = self.pool.get('hr.intervent.user.mode')

        # Create first page for private:
        if report_mode == 'private':
            ws_name = 'Ridotta'
            excel_pool.create_worksheet(ws_name)
            excel_pool.set_margins(ws_name, 0.3, 0.3)
            excel_pool.set_paper(ws_name) # Set A4
            excel_pool.fit_to_pages(ws_name, 1, 0)
            excel_pool.set_format(
                title_font='Arial', header_font='Arial', text_font='Arial')

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
                # picking.partner_id.name,
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
            ('date', '>=', '%s 00:00:00' % from_date),
            ('date', '<=', '%s 23:59:59' % to_date),
            # ('invoice_id', '=', False),  # Not Invoiced
            ]

        # Not invoiced only if not internal
        # if report_mode != 'report':
        #    domain.append(('is_invoiced', '=', False))
        if ddt_mode == 'ddt':
            domain.append(('is_invoiced', '=', False))
        # else:
        #    domain.append(('is_invoiced', '=', True))

        if contact_id:
            domain.append(('contact_id', '=', contact_id))

        if no_account:
            domain.append(('account_id', '=', False))
        elif account_id:
            domain.append(('account_id', '=', account_id))

        ddt_delivery_ids = set(ddt_pool.search(cr, uid, domain + [
            ('delivery_date', '>=', '%s 00:00:00' % from_date),
            ('delivery_date', '<=', '%s 23:59:59' % to_date),
            ], context=context))
        ddt_date_ids = set(ddt_pool.search(cr, uid, domain + [
            ('date', '>=', '%s 00:00:00' % from_date),
            ('date', '<=', '%s 23:59:59' % to_date),
            ], context=context))
        ddt_ids = tuple(ddt_delivery_ids | ddt_date_ids)
        _logger.warning('Delivery: %s, Date: %s, Total: %s' % (
            len(ddt_delivery_ids),
            len(ddt_date_ids),
            len(ddt_ids),
            ))

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
        # C. COLLECT INVOCE:
        # ---------------------------------------------------------------------
        invoice_db = {}
        for invoice in manual_invoice_ids:
            key = (
                invoice.date,
                )
            if key not in invoice_db:
                invoice_db[key] = []
            invoice_db[key].append(invoice)

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
                intervent.account_id.name,
                #intervent.date_start, # XXX error?
                #intervent.ref,
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
        # F. EXPENCES:
        # ---------------------------------------------------------------------
        # Domain:
        # TODO wizard parameter
        domain = [
            ('date', '>=', from_date),
            ('date', '<=', to_date),
            ('printable', '!=', 'none'),
            # TODO printable!
            ]

        # No account => all partner expences account
        if account_id:
            domain.append(('account_id', '=', account_id))
        else:
            domain.append(('account_id.partner_id', '=', partner_id))

        expence_ids = expence_pool.search(cr, uid, domain, context=context)
        expence_proxy = expence_pool.browse(
            cr, uid, expence_ids, context=context)
        expence_db = {}
        for expence in expence_proxy:
            key = (
                expence.account_id.name,
                expence.category_id.name,
                expence.date,
                )
            if key not in expence_db:
                expence_db[key] = []
            expence_db[key].append(expence)

        # ---------------------------------------------------------------------
        #                             EXCEL REPORT:
        # ---------------------------------------------------------------------
        sheets = {
            # -----------------------------------------------------------------
            # Summary sheet:
            # -----------------------------------------------------------------
            'Riepilogo': { # Summary
                'row': -1,
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
                    35, 20, 10, 15, 20, 15, 20,
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
                    30, 30, 15, 10, 20,
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
                    35, 20, 15, 10, 25, 35, 10,
                    15, 15, 15, 15,
                    20, 20, 20,
                    ],
                'total': {},
                'data': ddt_db,
                },

            'Fatture': { # DDT not invoiced
                'row': 0,
                'header': [
                    'Data', 'Commessa', 'Destinazione', 'Contatto', 'Rif.',
                    'Note', 'Totale',
                    ],
                'width': [
                    15, 20, 25, 25, 10, 40, 15,
                    ],
                'total': {},
                'data': invoice_db,
                },

            'Spese': {
                'row': 0,
                'header': [
                    'Data', 'Comessa', 'Categoria', 'Descrizione',
                    'Costo ultimo', 'Scontato', 'Totale',
                    ],
                'width': [
                    12, 20, 20, 30, 10,
                    ],
                'total': {},
                'data': expence_db,
                },

            'Materiali': { # List compress for code
                'row': 0,
                'header': [
                    'Codice', 'Descrizione', 'UM', 'Q.',
                    'Costo ultimo',
                    #'Scontato', 'METEL',
                    'Sub. ultimo',
                    #'Sub. scontato', 'Sub. METEL',
                    ],
                'width': [
                    15, 35, 7, 10,
                    15, 15, 15,
                    15, 15, 15,
                    ],
                #'total': {},
                #'data': ,
                },

            'Commesse': { # Account
                'row': 0,
                'header': ['Fatturazione', 'Codice', 'Commessa', 'Padre',
                    'Data', 'Posizione fiscale', 'Ore', 'Stato'],
                'width': [25, 10, 30, 20,
                    10, 20, 10, 10],
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

            'Fatture': {
                'header': ['Data', 'Riferimento', 'Totale'],
                'data': {},
                'total_cost': 0.0,
                'total_discount': 0.0,
                'total_revenue': 0.0,
                },

            # TODO Spese!!!
            'Spese': {
                'header': ['Commessa', 'Categoria', 'Costo', 'Scontato',
                    'Totale'],
                'data': {},
                'total_cost': 0.0,
                'total_discount': 0.0,
                'total_revenue': 0.0,
                },


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
            'Fatture',
            'Spese',
            'Commesse',
            'Materiali',
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
            excel_pool.set_margins(ws_name)
            excel_pool.set_paper(ws_name)  # Set A4
            # excel_pool.set_print_scale(ws_name, 90)
            excel_pool.fit_to_pages(ws_name, 1, 0)

            # Load formats:
            if load_format:
                excel_pool.set_format(
                    title_font='Arial', header_font='Arial', text_font='Arial')

                f_number = excel_pool.get_format('number')
                f_number_red = excel_pool.get_format('bg_red_number')

                f_title = excel_pool.get_format('title')
                f_header = excel_pool.get_format('header')

                f_text = excel_pool.get_format('text')
                f_text_red = excel_pool.get_format('bg_red')
                load_format = False # once!

            # Setup columns
            excel_pool.column_width(ws_name, sheet['width'])

            # Add title:
            if ws_name in ('Materiali', 'Riepilogo'):
                # Filter text:
                excel_pool.write_xls_line(ws_name, 0, [
                    filter_text,
                    ],default_format=f_title)
                sheet['row'] += 2


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
                    # document_total = 0.0
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
                                (product_name, list_price, standard_price,
                                    discount_price, discount_vat) = \
                                    product_pool.extract_product_data(
                                        cr, uid, move, context=context)

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
                                    formatLang(picking.min_date[:10]),
                                    picking.pick_state,

                                    # Move:
                                    move.product_id.default_code,
                                    product_name,
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
                                formatLang(picking.min_date[:10]),
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
                                    (product_name, list_price, standard_price,
                                        discount_price, discount_vat) = \
                                        product_pool.extract_product_data(
                                            cr, uid, move, context=context)

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
                                        (formatLang(
                                            ddt.delivery_date or ddt.date))[:10],

                                        # Move:
                                        product.default_code,
                                        product_name,
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


                            else:  # Picking no movements:
                                data = self.data_mask_filter([
                                    # Header
                                    ddt.account_id.name or 'NON ASSEGNATA',
                                    ddt.contact_id.name or '/',
                                    ddt.name,
                                    (formatLang(
                                        ddt.delivery_date or ddt.date))[:10],

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
                            (formatLang(
                                ddt.delivery_date or ddt.date))[:10],

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
        # C. INVOICE:
        # ---------------------------------------------------------------------
        if mask['Fatture'][0]:
            ws_name = 'Fatture'
            sheet = sheets[ws_name]
            summary_data = summary[ws_name]['data']

            total = sheet['total']
            for key in invoice_db:
                for invoice in invoice_db[key]:
                    invoice_total1 = 0.0
                    invoice_total2 = 0.0
                    invoice_total3 = 0.0
                    invoice_error = False

                    account = invoice.account_id
                    account_id = account.id
                    if account not in account_used:
                        account_used.append(account)
                    if account_id not in total:
                        total[account_id] = 0.0

                    subtotal3 = invoice.total
                    # ddt_total1 += subtotal1 ddt_total2 += subtotal2
                    invoice_total3 += subtotal3

                    data = self.data_mask_filter([
                        # Header
                        formatLang(invoice.date),
                        invoice.account_id.name,
                        invoice.address_id.name or '/',
                        invoice.contact_id.name or '/',
                        invoice.name,
                        invoice.note,
                        (subtotal3, f_number),
                        ], mask['Fatture'][1])

                    excel_pool.write_xls_line(
                        ws_name, sheet['row'], data,
                        default_format=f_text,
                        )
                    sheet['row'] += 1

                    # -----------------------------------------
                    #                    TOTALS:
                    # -----------------------------------------
                    # A. Total per account:
                    total[account_id] += subtotal3 # XXX

                    # B. Line total in same sheet:
                    # summary[ws_name][
                    #    'total_cost'] += subtotal1
                    # summary[ws_name][
                    #    'total_discount'] += subtotal2
                    summary[ws_name][
                        'total_revenue'] += subtotal3

                    # Summary data (picking):
                    block_key = (invoice.name)
                    if block_key not in summary_data:
                        summary_data[block_key] = []

                    summary_data[block_key].append((
                        formatLang(invoice.date),
                        (invoice.name, f_text),
                        (invoice_total3, f_number),
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
                    ], mask['Fatture'][2]),
                default_format=f_text, col=mask['Fatture'][3])

        # ---------------------------------------------------------------------
        # C. EXPENCE GROUPED BY:
        # ---------------------------------------------------------------------
        if mask['Spese'][0]:
            ws_name = 'Spese'
            sheet = sheets[ws_name]
            summary_data = summary[ws_name]['data']
            total = sheet['total']
            for key in expence_db:
                for expence in expence_db[key]:
                    account = expence.account_id
                    category = expence.category_id
                    subtotal1 = expence.total
                    subtotal2 = 0.0
                    subtotal3 = expence.total_forced or expence.total

                    if category.id not in total: # TODO
                        total[category.id] = 0.0

                    data = self.data_mask_filter([
                        account.name or '',
                        formatLang(expence.date),
                        category.name or '',
                        expence.name or '',
                        (subtotal1, f_number),
                        (subtotal2, f_number),
                        (subtotal3, f_number),
                        ], mask['Spese'][1])

                    excel_pool.write_xls_line(
                        ws_name, sheet['row'], data,
                        default_format=f_text,
                        )
                    sheet['row'] += 1

                    # ---------------------------------------------------------
                    # Summary data (expence):
                    # ---------------------------------------------------------
                    block_key = (account, category)
                    if block_key not in summary_data:
                        summary_data[block_key] = []

                    summary_data[block_key].append((
                        (account.name, f_text),
                        (category.name, f_text),
                        (subtotal1, f_number),
                        (subtotal2, f_number),
                        (subtotal3, f_number),
                        ))

                    # ---------------------------------------------------------
                    #                    TOTALS:
                    # ---------------------------------------------------------
                    # A. Total per account:
                    total[category.id] += subtotal1

                    # B. Line total in same sheet:
                    summary[ws_name]['total_cost'] += subtotal1
                    summary[ws_name]['total_discount'] += 0.0
                    summary[ws_name]['total_revenue'] += subtotal3

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
                    ], mask['Spese'][2]),
                default_format=f_text,
                col=mask['Spese'][3])

        # ---------------------------------------------------------------------
        # D. MATERIAL GROUPED BY:
        # ---------------------------------------------------------------------
        if mask['Materiali'][0]:
            ws_name = 'Materiali'
            sheet = sheets[ws_name]
            material_rows = {}

            # -----------------------------------------------------------------
            # Read picking:
            # -----------------------------------------------------------------
            for key in picking_db:
                for picking in picking_db[key]:
                    if picking.move_lines:
                        if picking.move_lines:
                            for move in picking.move_lines:
                                self.material_update(
                                    cr, uid, material_rows, move,
                                    context=context)

            # -----------------------------------------------------------------
            # Read DDT:
            # -----------------------------------------------------------------
            for key in ddt_db:
                for ddt in ddt_db[key]:
                    if ddt.picking_ids:
                        for picking in ddt.picking_ids:
                            if picking.move_lines:
                                for move in picking.move_lines:
                                    self.material_update(
                                        cr, uid, material_rows, move,
                                        context=context)

            # -----------------------------------------------------------------
            # Excel page Materiali: 1. Material
            # -----------------------------------------------------------------
            sub1 = sub2 = sub3 = 0.0
            for key in sorted(
                    material_rows, key=lambda x: x[0].default_code):
                record = material_rows[key]

                # Unpack data:
                (product, product_name, discount_price) = key

                data = self.data_mask_filter([
                    # Move:
                    product.default_code,
                    product_name,
                    move.product_uom.name,

                    (record[0], f_number),

                    (record[1], f_number),
                    (record[2], f_number),
                    (record[3], f_number),

                    (record[4], f_number),
                    (record[5], f_number),
                    (record[6], f_number),
                    ], mask['Materiali'][1])

                # Update total:
                sub1 += record[4]
                sub2 += record[5]
                sub3 += record[6]

                excel_pool.write_xls_line(
                    ws_name, sheet['row'], data,
                    default_format=f_text,
                    )
                sheet['row'] += 1

            # Total for block:
            data = self.data_mask_filter([
                ('Totale', f_title), '', '', '', '', '', '',
                sub1, sub2, sub3,
                ], mask['Materiali'][1])
            excel_pool.write_xls_line(
                ws_name, sheet['row'], data,
                default_format=f_number,
                )
            excel_pool.merge_cell(ws_name, [
                sheet['row'], 0, sheet['row'], 4,  # TODO parametrize on header
                ])

            # -----------------------------------------------------------------
            # Excel page Materiali: 2. Intervent
            # -----------------------------------------------------------------
            sub_amount = sub_h = 0.0
            if intervent_db:
                # Print header
                sheet['row'] += 2
                excel_pool.write_xls_line(
                    ws_name, sheet['row'], [
                        'Descrizione', 'Costo', 'H.',
                        ], default_format=f_header)

                sheet['row'] += 1

                for key in intervent_db:
                    for intervent in sorted(
                            intervent_db[key],
                            key=lambda x: x.date_start,
                            ):

                        # Remove not in report:
                        if intervent.not_in_report:
                            continue

                        # TODO Jump invoiced?
                        if intervent.is_invoiced:
                            continue

                        # -----------------------------------------------------
                        # Totals:
                        # -----------------------------------------------------
                        sub_amount -= intervent.amount
                        sub_h += intervent.unit_amount

                    # ---------------------------------------------------------
                    # Total line at the end of the block:
                    # ---------------------------------------------------------
                    excel_pool.write_xls_line(
                        ws_name, sheet['row'], [
                            'Interventi del periodo',
                            (sub_amount, f_number),
                            (sub_h, f_number),
                            ], default_format=f_text)

            # -----------------------------------------------------------------
            # Excel page Materiali: 3. Expences
            # -----------------------------------------------------------------
            subtotal1 = 0.0
            if expence_db:
                # Print header
                sheet['row'] += 2

                excel_pool.write_xls_line(
                    ws_name, sheet['row'], [
                        'Descrizione', 'Costo',
                        # 'Costo esposto',
                        ], default_format=f_header)

                sheet['row'] += 1
                for key in expence_db:
                    for expence in expence_db[key]:
                        subtotal1 += expence.total

                # Total:
                excel_pool.write_xls_line(
                    ws_name, sheet['row'], [
                        'Spese extra',
                        (subtotal1, f_number),
                        ], default_format=f_text,
                    )

            # Total cost:
            sheet['row'] += 2
            excel_pool.write_xls_line(
                ws_name, sheet['row'], [
                    'Tot. costi materiali, interventi e spese extra: EUR %s' % sum(
                        (sub1, subtotal1, sub_amount)),
                    ], default_format=f_title,
                )
        # ---------------------------------------------------------------------
        # E. INTERVENT:
        # ---------------------------------------------------------------------
        if mask['Interventi'][0]:  # Show / Hide page:
            ws_name = 'Interventi'
            sheet = sheets[ws_name]
            summary_data = summary[ws_name]['data']

            partner_forced = False  # update first time!

            total = sheet['total']
            cost = sheet['cost']

            for key in intervent_db:
                for intervent in sorted(
                        intervent_db[key],
                        key=lambda x: x.date_start,
                        ):
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
                    if user_mode_id in partner_forced:  # partner forced
                        unit_revenue = partner_forced[user_mode_id]
                    else: # read for default list:
                        unit_revenue = mode_pricelist.get(user_mode_id, 0.0)

                    if account and account not in account_used:
                        account_used.append(account)

                    if account_id not in total:
                        total[account_id] = 0.0
                        cost[account_id] = 0.0

                    # document_total = 0.0
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
                        formatLang(intervent.date_start[:10]),
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
                    # block_key = (account.name, intervent.ref)
                    block_key = (account.name, intervent.date_start)
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
        # F. ACCOUNT:
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
                        '' if not account.from_date else
                        formatLang(account.from_date)[:10],
                        '/',  # account.fiscal_position.name,
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
                    formatLang(account.from_date[:10]),
                    '/', # account.fiscal_position.name,
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

            for block in sheet_order[1:-2]:  # Jump TODO commesse?!?

                # Check if sheet must be created:
                if block in mask and not mask[block][0]:
                    continue

                block_record = summary[block]
                if not block_record['data']:
                    _logger.warning('No summary block %s' % block)
                    continue

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

                for key in sorted(block_record['data']):
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

            for block in sheet_order[1:-1]:
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
        #                            PRIVATE MODE:
        # ---------------------------------------------------------------------
        if report_mode == 'private':
            ws_name = 'Ridotta'
            row = 0

            partner = wiz_browse.partner_id  # For information
            company = partner.company_id

            f_number = excel_pool.get_format('number')
            f_number_red = excel_pool.get_format('bg_red_number')
            f_title = excel_pool.get_format('title')
            f_header = excel_pool.get_format('header')
            f_text = excel_pool.get_format('text')
            f_text_red = excel_pool.get_format('bg_red')

            # Setup columns
            excel_pool.column_width(ws_name, [14, 30, 5, 14, 12, 12])

            # -----------------------------------------------------------------
            # Insert Logo:
            logo_field = company.logo or company.partner_id.image
            data_image = excel_pool.clean_odoo_binary(logo_field)

            excel_pool.row_height(ws_name, (row, ), height=65)
            excel_pool.write_image(
                ws_name, row, 0,
                x_offset=0, y_offset=0,
                x_scale=0.25, y_scale=0.25,
                positioning=2,
                filename=False,
                data=data_image,
                tip='Logo',
                # url=False,
            )
            excel_pool.write_xls_line(ws_name, row, [
                '',
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
                u'%s' % partner.name,
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
            # Filter text (merge cell):
            excel_pool.merge_cell(ws_name, [row, 0, row, 5])
            excel_pool.write_xls_line(ws_name, row, [
                filter_text,
                ],default_format=f_title)

            private_summary = []

            # -----------------------------------------------------------------
            # A. STOCK MATERIAL:
            # -----------------------------------------------------------------
            if any(picking_db.values()):
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
                                # Extract data:
                                (product_name, list_price, standard_price,
                                    discount_price, discount_vat) = \
                                    product_pool.extract_product_data(
                                        cr, uid, move, context=context)

                                if activity_price == 'lst_price':
                                    price = list_price
                                elif activity_price == 'metel_sale':
                                    price = discount_price
                                else: # discount_vat
                                    price = discount_vat
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
                                    product_name,
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
            if any(ddt_db.values()):
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
                                    # Extract data:
                                    product = move.product_id
                                    (product_name, list_price, standard_price,
                                        discount_price, discount_vat) = \
                                        product_pool.extract_product_data(
                                            cr, uid, move, context=context)

                                    if activity_price == 'lst_price':
                                        price = list_price
                                    elif activity_price == 'metel_sale':
                                        price = discount_price
                                    else:  # metel_sale_vat
                                        price = discount_vat

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
                                        product_name,
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
            if any(intervent_db.values()):
                partner_forced = False  # update first time!
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
                        # 'Totale',
                        'Data', 'Intervento', 'H.', 'Utente', 'Prezzo totale',
                        ], default_format=f_header)

                for key in intervent_db:
                    for intervent in intervent_db[key]:
                        # Readability:
                        user = intervent.user_id
                        partner = intervent.intervent_partner_id
                        user_mode_id = intervent.user_mode_id.id

                        # -----------------------------------------------------
                        # Initial setup of mapping and forced price database:
                        # -----------------------------------------------------
                        if partner_forced == False:
                            partner_forced = {}
                            for forced in partner.mode_revenue_ids:
                                partner_forced[forced.mode_id.id] = \
                                    forced.list_price
                        # -----------------------------------------------------
                        # Read revenue:
                        if user_mode_id in partner_forced: # partner forced
                            unit_revenue = partner_forced[user_mode_id]
                        else: # read for default list:
                            unit_revenue = mode_pricelist.get(
                                user_mode_id, 0.0)

                        this_revenue = intervent.unit_amount * unit_revenue
                        # this_cost = -intervent.amount

                        if this_revenue:
                            f_number_color = f_number
                            f_text_color = f_text
                        else:
                            f_number_color = f_number_red
                            f_text_color = f_text_red
                            ddt_error = True

                        data = [
                            formatLang(intervent.date_start[:10]),
                            intervent.name,
                            intervent.intervent_total,
                            user.name,
                            #intervent.intervent_duration intervent.unit_amount
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
            ('partner', 'Lista clienti'),  # List customer touched
            ('report', 'Stampa interna'),  # Internal detail (ex customer)

            # Client:
            ('detail', 'Dettagliata cliente'),
            ('summary', 'Riepilogativa cliente'),

            ('private', 'Stampa cliente'),
            ('user', u'Attività Tecnici'),
            ], 'Mode', required=True),

        'partner_id': fields.many2one(
            'res.partner', 'Partner'),
        'contact_id': fields.many2one(
            'res.partner', 'Contact'),
        'user_id': fields.many2one(
            'res.users', 'Operatore'),

        'account_id': fields.many2one(
            'account.analytic.account', 'Account'),
        'no_account': fields.boolean('No account'),

        'from_date': fields.date('From date >= ', required=True),
        'to_date': fields.date('To date <=', required=True),
        'float_time': fields.boolean('Formatted hour',
            help='If checked print hour in HH:MM format'),

        # DDT management:
        'ddt_mode': fields.selection([
            ('ddt', 'DDT non fatturati'),
            ('all', 'Tutto'),
            ], 'Modo DDT', required=True,
            help='Stampa anche i DDT non fatturati o fatturati'),

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
            ('metel_sale_vat', 'Discount price VAT'),
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
        'ddt_mode': lambda *x: 'ddt',
        'intervent_mode': lambda *x: 'pending',
        }

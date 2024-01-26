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
import pdb
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

report_page_name = {
    'private': 'Interna',
    'report': 'Dettaglio',
    'detail': 'Riassuntiva',
    'summary': 'Cliente',
}


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
        # Utilty:
        def parse_hours(total, dow_name, excel_format, none_color='grey'):
            """ Parse hours
            """
            if total:
                if dow_name in ('Dom.', 'Sab.'):
                    extra = total
                else:
                    extra = max(0.0, total - 8.0)
                ordinary = total - extra

                if total == 8.0:
                    excel_color = excel_format['green']
                elif total >= 10.0:
                    excel_color = excel_format['yellow']
                elif extra > 0:
                    excel_color = excel_format['blue']
                else:
                    excel_color = excel_format['red']
            else:  # Day without data
                total = ordinary = extra = ''
                excel_color = excel_format[none_color]
            return total, ordinary, extra, excel_color

        # ---------------------------------------------------------------------
        #                         Procedure start:
        # ---------------------------------------------------------------------
        if not context:
            context = {}
        collect_mode = context.get('collect_mode')

        report_mode = wiz_browse.mode

        dow = {
            0: 'Lun.',
            1: 'Mar.',
            2: 'Mer.',
            3: 'Gio.',
            4: 'Ven.',
            5: 'Sab.',
            6: 'Dom.',
        }
        intervent_pool = self.pool.get('hr.analytic.timesheet')
        user_pool = self.pool.get('res.users')

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
        row_date = []  # For user report
        header_date = {}
        header_date_text = []
        this_date = datetime.strptime(
            from_date[:10], DEFAULT_SERVER_DATE_FORMAT)
        this_end_date = datetime.strptime(
            to_date[:10], DEFAULT_SERVER_DATE_FORMAT)
        counter = 1
        while this_date <= this_end_date:
            this_date_text = this_date.strftime(DEFAULT_SERVER_DATE_FORMAT)
            dow_text = dow.get(this_date.weekday())
            header_date[this_date_text] = counter, dow_text
            header_date_text.append('%s\n%s' % (
                '%s/%s/%s' % (
                    this_date_text[-2:],
                    this_date_text[5:7],
                    this_date_text[:4],
                    ),
                dow_text,
                ))
            row_date.append((
                this_date_text,
                dow_text,
                ))
            this_date += timedelta(days=1)
            counter += 1

        domain = [
            ('date_start', '>=', '%s 00:00:00' % from_date),
            ('date_start', '<=', '%s 23:59:59' % to_date),
        ]
        if user_id and report_mode == 'user':
            domain.append(
                ('user_id', '=', user_id),
                )

        # ---------------------------------------------------------------------
        # Excel create:
        # ---------------------------------------------------------------------
        # Activity detail:
        # ---------------------------------------------------------------------
        excel_pool = self.pool.get('excel.writer')

        ws_name = u'Attività utente'
        excel_pool.create_worksheet(ws_name)

        # Load formats:
        excel_format = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),
            'white': {
                'text': excel_pool.get_format('text'),
                'number': excel_pool.get_format('number'),
                },
            'red': {
                'text': excel_pool.get_format('bg_red'),
                'number': excel_pool.get_format('bg_red_number'),
                },
            'green': {
                'text': excel_pool.get_format('bg_green'),
                'number': excel_pool.get_format('bg_green_number'),
                },
            'grey': {
                'text': excel_pool.get_format('bg_grey'),
                'number': excel_pool.get_format('bg_grey_number'),
                },
            'blue': {
                'text': excel_pool.get_format('bg_blue'),
                'number': excel_pool.get_format('bg_blue_number'),
                },
            'yellow': {
                'text': excel_pool.get_format('bg_yellow'),
                'number': excel_pool.get_format('bg_yellow_number'),
                },
            }

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
            ws_name, row, header, default_format=excel_format['header'])
        excel_pool.autofilter(ws_name, row, 0, row, len(header))
        excel_pool.freeze_panes(ws_name, 1, 2)

        # Collect data:
        summary_db = {}
        intervent_ids = intervent_pool.search(
            cr, uid, domain, context=context)
        intervent_proxy = intervent_pool.browse(
            cr, uid, intervent_ids, context=context)
        for intervent in sorted(intervent_proxy, key=lambda i: i.date_start):
            row += 1

            # Collect summary:
            user = intervent.user_id
            date = str(intervent.date_start)[:10]
            total_h = intervent.intervent_total  # Manual total used

            if user not in summary_db:
                summary_db[user] = {}
            if date not in summary_db[user]:
                summary_db[user][date] = 0.0
            summary_db[user][date] += total_h

            excel_pool.write_xls_line(
                ws_name, row, [
                    user.name or '',
                    intervent.date_start or '',
                    total_h or '',
                    intervent.ref or '',
                    mode_convert.get(intervent.mode, ''),
                    intervent.intervent_partner_id.name or '',
                    intervent.account_id.name or '',
                    intervent.account_id.partner_id.city or '',
                    intervent.account_id.partner_id.state_id.name or '',
                    intervent.name or '',
                    intervent.intervention or '',
                    ], default_format=excel_format['white']['text'])

        # ---------------------------------------------------------------------
        #                        Summary page:
        # ---------------------------------------------------------------------
        if report_mode == 'user':
            ws_name = u'Riepilogo'
            excel_pool.create_worksheet(ws_name)
            header = [
                'Data', 'Giorno',
                'H. totali', 'H. ordinarie', 'H. extra',
                ]
            width = [
                12, 5,
                10, 10, 10,
                ]
            excel_pool.column_width(ws_name, width)

            row = 0
            for user in summary_db:
                if row:  # Jump first line
                    row += 1
                excel_pool.write_xls_line(
                    ws_name, row, [
                        user.name or '',
                    ], default_format=excel_format['title'])
                excel_pool.merge_cell(ws_name, [row, 0, row, 4])

                row += 1
                excel_pool.write_xls_line(
                    ws_name, row, header,
                    default_format=excel_format['header'])
                master_total = [0.0, 0.0, 0.0]

                for record in row_date:
                    day, dow_name = record
                    row += 1

                    total = summary_db[user].get(day)
                    total, ordinary, extra, excel_color = \
                        parse_hours(total, dow_name, excel_format)
                    if total:
                        master_total[0] += total
                        master_total[1] += ordinary
                        master_total[2] += extra

                    excel_pool.write_xls_line(
                        ws_name, row, [
                            day,
                            dow_name,
                            (total, excel_color['number']),
                            (ordinary, excel_color['number']),
                            (extra or '', excel_color['number']),
                        ], default_format=excel_color['text'])

                # Total:
                row += 1
                excel_pool.merge_cell(ws_name, [row, 0, row, 1])
                excel_pool.write_xls_line(
                    ws_name, row, [
                        'TOTALE:',
                        '',
                        (master_total[0], excel_format['white']['number']),
                        (master_total[1], excel_format['white']['number']),
                        (master_total[2], excel_format['white']['number']),
                    ], default_format=excel_format['white']['text'])

        # ---------------------------------------------------------------------
        #                        Foglio presenze:
        # ---------------------------------------------------------------------
        elif report_mode == 'timesheet':
            ws_name = u'Foglio presenze'
            excel_pool.create_worksheet(ws_name)

            row = 0
            header = [
                'Operatore',
                'Tot. H', 'Ord. H', 'Extra H'
                ]
            fixed_cols = len(header)
            header.extend(header_date_text)

            width = [
                25, 6, 6, 6,
                ]
            width.extend([9 for i in range(len(header_date))])

            excel_pool.column_width(ws_name, width)
            excel_pool.row_height(ws_name, [row], height=30)
            excel_pool.write_xls_line(
                ws_name, row, header,
                default_format=excel_format['header'])
            excel_pool.freeze_panes(ws_name, 1, 1)

            for user in sorted(summary_db, key=lambda u: u.name):
                row += 1
                excel_pool.write_xls_line(
                    ws_name, row, [
                        user.name or '',
                    ], default_format=excel_format['white']['text'])

                master_total = [0.0, 0.0, 0.0]
                for day in header_date:
                    counter, dow_name = header_date[day]
                    pos = fixed_cols + counter - 1
                    total = summary_db[user].get(day, '')

                    total, ordinary, extra, excel_color = \
                        parse_hours(total, dow_name, excel_format,
                                    none_color='white')
                    master_total[0] += total or 0.0
                    master_total[1] += ordinary or 0.0
                    master_total[2] += extra or 0.0

                    excel_pool.write_xls_line(
                        ws_name, row, [total],
                        default_format=excel_color['number'],
                        col=pos)

                # Master total:
                pos = 1  # 2-4 column position
                excel_pool.write_xls_line(
                    ws_name, row, master_total,
                    default_format=excel_color['number'],
                    col=pos)
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
    def action_print_touched_store(self, cr, uid, ids, context=None):
        """ Store report data
        """
        store_pool = self.pool.get('res.partner.activity.storage')
        model_pool = self.pool.get('ir.model.data')

        if context is None:
            context = {}
        context['collect_mode'] = True

        # Create a wizard for call report element
        if ids:  # Comes from wizard (selected month)
            this_wizard = self.browse(cr, uid, ids, context=context)[0]
            from_month = this_wizard.from_date[:7]
            to_month = this_wizard.to_date[:7]
            names = []
            while from_month <= to_month:
                names.append(from_month)  # Always append fist date
                # Generate next month
                part = from_month.split('-')
                current_year = int(part[0])
                current_month = int(part[1])

                if current_month == 12:
                    current_year += 1
                    current_month = 1
                else:
                    current_month += 1
                from_month = '%04d-%02d' % (current_year, current_month)

            # todo Generate name list
        else:  # Updated from scheduled (current month)
            now = datetime.now()
            names = [now.strftime('%Y-%m')]

        _logger.info('Generating this months: %s' % (names, ))
        selected_ids = []  # List of touched:
        for name in names:
            _logger.info('Generating this month: %s' % name)
            name_part = name.split('-')
            year = int(name_part[0])
            month = int(name_part[1])
            if month == 12:
                new_month = 1
                new_year = year + 1
            else:
                new_month = month + 1
                new_year = year

            from_date = '%s-01' % name
            to_date = '%04d-%02d-01' % (new_year, new_month)
            to_date_dt = datetime.strptime(to_date, DEFAULT_SERVER_DATE_FORMAT)
            to_date = (to_date_dt - timedelta(days=1)).strftime(
                DEFAULT_SERVER_DATE_FORMAT)

            _logger.info('Generating stored data from %s to %s' % (
                from_date, to_date))

            wizard_id = self.create(cr, uid, {
                'from_date': from_date,
                'to_date': to_date,
                'mode': 'partner',

                'picking_mode': 'all',
                'ddt_mode': 'all',  # 'ddt',  # Not invoiced (not all!)
                'intervent_mode': 'all',   # 'pending',
            }, context=context)

            # Call original report with parameter:
            res = self.action_print_touched(
                cr, uid, [wizard_id], context=context)

            # -----------------------------------------------------------------
            #                        Collect detail:
            # -----------------------------------------------------------------
            keys = {}
            empty_key = {
                'total_intervent_draft': 0,
                'total_intervent_invoice': 0,
                'total_picking': 0,
                'total_ddt_draft': 0,
                'total_ddt_invoice': 0,
                'total_invoice': 0,

                # todo Totals (not filled for now):
                'amount_intervent': 0.0,
                'amount_picking': 0.0,
                'amount_ddt': 0.0,
                'amount_invoice': 0.0,
            }

            # Intervent:
            intervents = res.get('intervent', ())
            for intervent in intervents:
                key = (
                    intervent.intervent_partner_id.id or False,
                    intervent.account_id.id or False,
                    intervent.intervent_contact_id.id or False,
                )
                if key not in keys:
                    keys[key] = empty_key.copy()

                if intervent.is_invoiced:
                    keys[key]['total_intervent_invoice'] += 1
                else:
                    keys[key]['total_intervent_draft'] += 1

            # Picking:
            pickings = res.get('picking', ())
            for picking in pickings:
                key = (
                    picking.partner_id.id or False,
                    picking.account_id.id or False,
                    picking.contact_id.id or False,
                )
                if key not in keys:
                    keys[key] = empty_key.copy()

                keys[key]['total_picking'] += 1

            # DDT:
            ddts = res.get('ddt', ())
            for ddt in ddts:
                key = (
                    ddt.partner_id.id or False,
                    ddt.account_id.id or False,
                    ddt.contact_id.id or False,
                )
                if key not in keys:
                    keys[key] = empty_key.copy()

                if ddt.is_invoiced:
                    keys[key]['total_ddt_invoice'] += 1
                else:
                    keys[key]['total_ddt_draft'] += 1

            # -----------------------------------------------------------------
            # Load this month from store:
            # -----------------------------------------------------------------
            store_ids = store_pool.search(cr, uid, [
                ('name', '=', name),
             ], context=context)
            store_db = {}
            for store in store_pool.browse(
                    cr, uid, store_ids, context=context):
                key = (
                    store.partner_id.id or False,
                    store.account_id.id or False,
                    store.contact_id.id or False,
                    )
                store_db[key] = store.id  # keep store?

            # todo for now used only Account page
            # Update data in stored items
            for key in keys:
                partner_id, account_id, contact_id = key
                record = keys[key]

                data = {
                    'name': name,
                    'from_date': from_date,
                    'to_date': to_date,
                    'partner_id': partner_id,
                    'account_id': account_id,
                    'contact_id': contact_id,
                    # 'stage_id':

                    # todo not used: Check:
                    # 'check_intervent': has_intervent,
                    # 'check_stock': has_picking,
                    # 'check_ddt': has_ddt,
                    # 'check_invoice': False,  # todo never Invoice?
                }
                data.update(record)  # Add total fields

                record_id = store_db.get(key)
                if record_id:
                    # todo only if theres' difference?
                    store_pool.write(
                        cr, uid, [record_id], data, context=context)
                    del(store_db[key])
                else:
                    record_id = store_pool.create(
                        cr, uid, data, context=context)
                selected_ids.append(record_id)
                # todo generate file?

            # Deleting no more records:
            for key in store_db:
                remove_id = store_db[key]
                store_pool.unlink(cr, uid, [remove_id], context=context)
                # todo delete linked file

        # ---------------------------------------------------------------------
        # Return selected elements in a tree:
        # ---------------------------------------------------------------------
        if not selected_ids:
            return True

        # form_view_id = False
        tree_view_id = model_pool.get_object_reference(
            cr, uid,
            'electrical_customer_activity',
            'view_res_partner_activity_storage_tree',
            )[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Record selezionati'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            # 'res_id': ids[0],
            'res_model': 'res.partner.activity.storage',
            'view_id': tree_view_id,  # False
            'views': [(tree_view_id, 'tree')],  # , (form_view_id, 'form')
            'domain': [('id', 'in', selected_ids)],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    def action_print_touched(self, cr, uid, ids, context=None):
        """ List of partner touched in that period
            context:
               - collect_mode: run in collect mode, return detail not report

        """
        if not context:
            context = {}
        collect_mode = context.get('collect_mode')

        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        from_date = wiz_browse.from_date
        to_date = wiz_browse.to_date

        intervent_mode = wiz_browse.intervent_mode

        # ---------------------------------------------------------------------
        # Pool used:
        # ---------------------------------------------------------------------
        excel_pool = self.pool.get('excel.writer')

        partner_pool = self.pool.get('res.partner')
        picking_pool = self.pool.get('stock.picking')
        ddt_pool = self.pool.get('stock.ddt')
        # invoice_pool = self.pool.get('account.invoice')
        account_pool = self.pool.get('account.analytic.account')
        intervent_pool = self.pool.get('hr.analytic.timesheet')

        if not collect_mode:
            partner_set = set()
            contact_set = set()
            account_set = set()

        # ---------------------------------------------------------------------
        # A. Picking partner:
        # ---------------------------------------------------------------------
        domain = [
            ('min_date', '>=', '%s 00:00:00' % from_date),
            ('min_date', '<=', '%s 23:59:59' % to_date),
            ('ddt_id', '=', False),  # Not DDT
            ('pick_move', '=', 'out'),  # Only out movement
            ]

        picking_ids = picking_pool.search(cr, uid, domain, context=context)
        picking_proxy = picking_pool.browse(
            cr, uid, picking_ids, context=context)

        if not collect_mode:
            # Partner:
            picking_partner_ids = [
                item.partner_id.id for item in picking_proxy]
            partner_set.update(set(tuple(picking_partner_ids)))

            # Contact:
            picking_contact_ids = [
                item.contact_id.id for item in picking_proxy]
            contact_set.update(set(tuple(picking_contact_ids)))

            # Account:
            picking_account_ids = [
                item.account_id.id for item in picking_proxy]
            account_set.update(set(tuple(picking_account_ids)))

        # ---------------------------------------------------------------------
        # B. DDT:
        # ---------------------------------------------------------------------
        # 2 search for different date value
        domain = [
            ('delivery_date', '>=', '%s 00:00:00' % from_date),
            ('delivery_date', '<=', '%s 23:59:59' % to_date),
            ]
        if not collect_mode:
            # Collect mode read all DDT (split after)
            domain.append(('is_invoiced', '=', False))

        ddt_delivery_ids = set(
            ddt_pool.search(cr, uid, domain, context=context))

        domain = [
            ('date', '>=', '%s 00:00:00' % from_date),
            ('date', '<=', '%s 23:59:59' % to_date),
            ]
        if not collect_mode:
            # Collect mode read all DDT (split after)
            domain.append(('is_invoiced', '=', False))

        ddt_date_ids = set(
            ddt_pool.search(cr, uid, domain, context=context))
        ddt_ids = tuple(ddt_delivery_ids | ddt_date_ids)
        _logger.warning('List Delivery: %s, Date: %s, Total: %s' % (
            len(ddt_delivery_ids),
            len(ddt_date_ids),
            len(ddt_ids),
            ))

        ddt_proxy = ddt_pool.browse(cr, uid, ddt_ids, context=context)

        if not collect_mode:
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
        # D. Intervention:
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

        if not collect_mode:
            # Partner
            intervent_partner_ids = [item.intervent_partner_id.id for item in
                                     intervent_proxy]
            partner_set.update(set(tuple(intervent_partner_ids)))

            # Contact
            intervent_contact_ids = [item.intervent_contact_id.id for item in
                                     intervent_proxy]
            contact_set.update(set(tuple(intervent_contact_ids)))

            # Account:
            intervent_account_ids = [item.account_id.id for item in
                                     intervent_proxy]
            account_set.update(set(tuple(intervent_account_ids)))

        # ---------------------------------------------------------------------
        # End of collect mode procedure:
        # ---------------------------------------------------------------------
        if collect_mode:
            return {
                'intervent': intervent_proxy,
                'picking': picking_proxy,
                'ddt': ddt_proxy,
                # 'invoice': intervent_proxy,
            }

        # ---------------------------------------------------------------------
        #                         Excel report:
        # ---------------------------------------------------------------------
        # Partner:
        ws_name = 'Partner'
        row = 0
        header = [
            'Partner', 'Consegne', 'DDT',
            # 'Fatture',
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

            # -----------------------------------------------------------------
            # 2 Mode report:
            # -----------------------------------------------------------------
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
            # 'Fatture',
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
                # partner_id in invoice_partner_ids,
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
        def get_ws_name(ws_name, report_mode, multi):
            """ return ws_name for multi
            """
            if not multi:
                return ws_name

            # todo move away:
            return '%s-%s' % (
                report_page_name.get(report_mode, '0'),
                ws_name,
            )

        if context is None:
            context = {}
        save_fullname = context.get('save_fullname')

        # Mapping text (for readability):
        pick_state_map = {
            'todo': 'Da fare',
            'ready': 'Pronte',
            'delivered': 'Consegnato',
            }

        # ---------------------------------------------------------------------
        # Pool used:
        # ---------------------------------------------------------------------
        excel_pool = self.pool.get('excel.writer')

        # Account:
        picking_pool = self.pool.get('stock.picking')
        ddt_pool = self.pool.get('stock.ddt')
        account_pool = self.pool.get('account.analytic.account')
        product_pool = self.pool.get('product.product')
        expence_pool = self.pool.get('account.analytic.expence')
        # invoice_pool = self.pool.get('account.invoice')

        # Interventi:
        intervent_pool = self.pool.get('hr.analytic.timesheet')
        mode_pool = self.pool.get('hr.intervent.user.mode')

        # Wizard parameters:
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        partner_id = wiz_browse.partner_id.id  # Mandatory:
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
        picking_mode = wiz_browse.picking_mode
        ddt_mode = wiz_browse.ddt_mode
        mark_invoiced = wiz_browse.mark_invoiced

        partner_text = 'Cliente: %s, ' % wiz_browse.partner_id.name
        # todo intervent_mode, ddt_mode
        filter_text = \
            'Interventi del periodo: [%s - %s], %s' \
            'Contatto: %s, Commessa: %s%s' % (
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

        # ---------------------------------------------------------------------
        # Redirect report for user in another procedure:
        # ---------------------------------------------------------------------
        # A. Customer report different setup (not in this procedure):
        if report_mode in ('user', 'timesheet'):
            # >>> Call different report procedure:
            return self.extract_user_activity(
                cr, uid, wiz_browse, context=context)

        # Report complete (only for 4 report here!):
        if report_mode == 'complete':
            report_mode_loop = ['report', 'detail', 'summary', 'private']
            multi = True
        else:
            report_mode_loop = [report_mode]
            multi = False

        # =====================================================================
        #                            Startup:
        # =====================================================================
        # Load mode pricelist (to get revenue):
        mode_pricelist = {}
        mode_ids = mode_pool.search(cr, uid, [], context=context)
        for mode in mode_pool.browse(
                cr, uid, mode_ids, context=context):
            mode_pricelist[mode.id] = mode.list_price

        # =====================================================================
        #                    COLLECT ALL REPORT DATA:
        # =====================================================================
        account_used = []

        # ---------------------------------------------------------------------
        # A. COLLECT STOCK MATERIAL:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('partner_id', '=', partner_id),
            ('min_date', '>=', '%s 00:00:00' % from_date),
            ('min_date', '<=', '%s 23:59:59' % to_date),
            ('ddt_id', '=', False),  # Not DDT
            ('pick_move', '=', 'out'),  # Only out movement
            ]

        # Wizard parameters:
        if picking_mode == 'todo':
            domain.append(
                ('pick_state', 'in', ('todo', 'ready')))
        elif picking_mode == 'delivered':
            domain.append(
                ('pick_state', '=', 'delivered'))
        # else = all

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
        if ddt_mode == 'ddt':
            domain.append(('is_invoiced', '=', False))

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
                # ddt.partner_id.name,
                ddt.account_id.name,
                ddt.name,
                )
            if key not in ddt_db:
                ddt_db[key] = []
            ddt_db[key].append(ddt)

        # ---------------------------------------------------------------------
        # C. COLLECT INVOICE:
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
        # D. COLLECT INTERVENTION:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('intervent_partner_id', '=', partner_id),
            ('date_start', '>=', from_date),
            ('date_start', '<=', to_date),
            # ('account_id.is_extra_report', '=', False),
            ]
        # todo manage ticket here?

        if contact_id:
            domain.append(('intervent_contact_id', '=', contact_id))

        if no_account:
            domain.append(('account_id', '=', False))
        elif account_id:
            domain.append(('account_id', '=', account_id))

        # Manage filter on invoiced intervention:
        if intervent_mode == 'invoiced':
            domain.append(('is_invoiced', '=', True))
        elif intervent_mode == 'pending':
            domain.append(('is_invoiced', '=', False))
        # todo summary, detail

        intervent_ids = intervent_pool.search(cr, uid, domain, context=context)
        intervent_proxy = intervent_pool.browse(
            cr, uid, intervent_ids, context=context)
        intervent_db = {}
        for intervent in intervent_proxy:
            key = (
                intervent.account_id.name,
                # intervent.date_start, # XXX error?
                # intervent.ref,
                )
            if key not in intervent_db:
                intervent_db[key] = []
            intervent_db[key].append(intervent)

        # Wizard force operation:
        if mark_invoiced and intervent_ids:
            intervent_pool.write(cr, uid, intervent_ids, {
                'is_invoiced': True,
                }, context=context)
            _logger.warning('Update as invoices %s intervent' % len(
                intervent_ids))

        # ---------------------------------------------------------------------
        # E. COLLECT ACCOUNTING DATA:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('partner_id', '=', partner_id),
            ]
        # XXX Note: Contacts don't have account!

        account_ids = account_pool.search(cr, uid, domain, context=context)
        account_proxy = account_pool.browse(
            cr, uid, account_ids, context=context)
        account_db = {}
        for account in account_proxy:
            key = (
                # account.partner_id.name,
                account.account_mode,
                account.name,
                )
            if key not in account_db:
                account_db[key] = []
            account_db[key].append(account)

        # ---------------------------------------------------------------------
        # F. EXTRA EXPENSES:
        # ---------------------------------------------------------------------
        # Domain:
        # todo wizard parameter
        domain = [
            ('date', '>=', from_date),
            ('date', '<=', to_date),
            ('printable', '!=', 'none'),
            # todo printable!
            ]

        # No account => all partner expenses account
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

        # =====================================================================
        #                             EXCEL REPORT:
        # =====================================================================
        # Master loop:
        # =====================================================================
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
        load_format = True  # For load only first loop

        for report_mode in report_mode_loop:
            # -----------------------------------------------------------------
            # Setup dictionary (reset every loop!):
            # -----------------------------------------------------------------
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
                    True, '',  # Hide block, Col Hide
                    '', 18,  # Total line hide, Total position
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

            # Create first page only for private mode:
            if report_mode == 'private':
                ws_name = 'Ridotta'  # Only this page in private
                ws_name_ref = get_ws_name(ws_name, report_mode, multi)

                excel_pool.create_worksheet(ws_name_ref)
                excel_pool.set_margins(ws_name_ref, 0.3, 0.3)
                excel_pool.set_paper(ws_name_ref)  # Set A4
                excel_pool.fit_to_pages(ws_name_ref, 1, 0)
                excel_pool.set_format(
                    title_font='Arial', header_font='Arial', text_font='Arial')

            # -----------------------------------------------------------------
            #                  Setup depend on report mode:
            # -----------------------------------------------------------------
            # B.: Other 3 report mode:
            # Setup columns printed and other custom part depend on mode:
            if report_mode in ('detail', 'summary'):
                # -------------------------------------------------------------
                # Hide page:
                # -------------------------------------------------------------
                # mask['Interventi'][0] = False
                mask['DDT'][0] = False
                mask['Commesse'][0] = False

                # -------------------------------------------------------------
                # Hide columns:
                # -------------------------------------------------------------
                mask['Interventi'][1] = '011100010010000110010000'
                mask['Consegne'][1] = '000011111001001'
                mask['DDT'][1] = ''
                # mask['Fatture'][1] = ''
                # mask['Riepilogo'][1] = ''
                # mask['Commesse'][1] = ''

                # -------------------------------------------------------------
                # Total block:
                # -------------------------------------------------------------
                mask['Consegne'][2] = '001'
                mask['Consegne'][3] = 5

                mask['Interventi'][2] = '01'
                mask['Interventi'][3] = 7

                # -------------------------------------------------------------
                # Summary mask
                # -------------------------------------------------------------
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
                else:  # detail
                    # Summary line:
                    mask['Interventi'][4] = '1101'
                    mask['Consegne'][4] = '11001'
                    mask['DDT'][4] = '11001'

                    # Summary total:
                    mask['Interventi'][5] = '01'
                    mask['Consegne'][5] = '001'
                    mask['DDT'][5] = '001'

                # -------------------------------------------------------------
                # Total table:
                # -------------------------------------------------------------
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

            sheets = {
                # -------------------------------------------------------------
                # Summary sheet:
                # -------------------------------------------------------------
                'Riepilogo': {  # Summary
                    'row': -1,
                    'header': [],
                    'width': [40, 25, 15, 15, 15],
                    'data': True,  # Create sheet
                    },

                # -------------------------------------------------------------
                # Sheet detail:
                # -------------------------------------------------------------
                'Interventi': {  # Invertent list
                    'row': 0,
                    'header': self.data_mask_filter([
                        'Commessa', 'Contatto', 'Data', 'Intervento',
                        'Oggetto',
                        'Modo', 'Operazione',
                        'Utente', 'Durata', 'Indicate', 'Totale ore',
                        'Viaggio', 'H. Viaggio', 'Pausa', 'H. Pausa',
                        'Richiesta', 'Intervento', 'Note',
                        'Costo',
                        # Not used:
                        'Prezzo totale', 'Conteggio', 'Non usare',
                        'Stato', 'Fatt.',
                        ], mask['Interventi'][1]),
                    'width': self.data_mask_filter([
                        35, 20, 10, 15, 20, 15,
                        20,
                        20, 10, 10, 10,
                        3, 10, 3, 10,
                        30, 30, 30,
                        10, 10, 10, 5, 15, 5,
                        ], mask['Interventi'][1]),
                    'total': {},
                    'cost': {},
                    'data': intervent_db,
                    },

                'Consegne': {  # Picking to delivery
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

                'DDT': {  # DDT not invoiced
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

                'Fatture': {  # DDT not invoiced
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
                        'Data', 'Commessa', 'Categoria', 'Descrizione',
                        'Costo ultimo', 'Scontato', 'Totale',
                        ],
                    'width': [
                        12, 30, 20, 30, 10,
                        ],
                    'total': {},
                    'data': expence_db,
                    },

                'Materiali': {  # List compress for code
                    'row': 0,
                    'header': [
                        'Codice', 'Descrizione', 'UM', 'Q.',
                        'Costo ultimo',
                        # 'Scontato', 'METEL',
                        'Sub. ultimo',
                        # 'Sub. scontato', 'Sub. METEL',
                        ],
                    'width': [
                        15, 35, 7, 10,
                        15, 15, 15,
                        15, 15, 15,
                        ],
                    # 'total': {},
                    # 'data': ,
                    },

                'Commesse': {  # Account
                    'row': 0,
                    'header': [
                        'Fatturazione', 'Codice', 'Commessa', 'Padre',
                        'Data', 'Posizione fiscale', 'Ore', 'Stato'],
                    'width': [
                        25, 10, 30, 20,
                        10, 20, 10, 10],
                    'total': {},
                    'data': account_db,
                    },
                }

            # -----------------------------------------------------------------
            # First page: Summary blocks
            # -----------------------------------------------------------------
            # Reset every loop:
            summary = {
                'Interventi': {
                    'header': ['Commessa', 'Intervento', 'Costo', 'Totale'],
                    'data': {},
                    'total_cost': 0.0,
                    # 'total_discount': 0.0,
                    'total_revenue': 0.0,
                    },

                'Consegne': {
                    'header': [
                        'Commessa', 'Picking', 'Costo', 'Scontato', 'Totale'],
                    'data': {},
                    'total_cost': 0.0,
                    'total_discount': 0.0,
                    'total_revenue': 0.0,
                    },

                'DDT': {
                    'header': [
                        'Commessa', 'DDT', 'Costo', 'Scontato', 'Totale'],
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

                'Spese': {
                    'header': [
                        'Commessa', 'Categoria', 'Costo', 'Scontato',
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
                    # 'total_discount': 0.0,
                    'total_revenue': 0.0,
                    },
                }

            # -----------------------------------------------------------------
            #                 Excel setup format for list:
            # -----------------------------------------------------------------
            for ws_name in sheet_order:
                ws_name_ref = get_ws_name(ws_name, report_mode, multi)

                # Check if sheet must be created:
                # Note: every report loop reset to original value!
                if ws_name in mask and not mask[ws_name][0]:
                    continue

                #  Sheet setup for this report (row, header, summary...)
                # Note: every report loop reset to original value!
                sheet = sheets[ws_name]

                # if not sheet['data']:
                #    continue # No sheet creation

                # Create sheet:
                excel_pool.create_worksheet(ws_name_ref)
                excel_pool.set_margins(ws_name_ref)
                excel_pool.set_paper(ws_name_ref)  # Set A4
                # excel_pool.set_print_scale(ws_name_ref, 90)
                excel_pool.fit_to_pages(ws_name_ref, 1, 0)

                # Load formats:
                if load_format:  # Only first loop!
                    excel_pool.set_format(
                        title_font='Arial', header_font='Arial',
                        text_font='Arial')

                    f_number = excel_pool.get_format('number')
                    f_number_red = excel_pool.get_format('bg_red_number')

                    f_title = excel_pool.get_format('title')
                    f_header = excel_pool.get_format('header')

                    f_text = excel_pool.get_format('text')
                    f_text_red = excel_pool.get_format('bg_red')
                    load_format = False  # once!

                # Setup columns
                excel_pool.column_width(ws_name_ref, sheet['width'])

                # Add title:
                if ws_name in ('Materiali', 'Riepilogo'):
                    # Filter text:
                    excel_pool.write_xls_line(ws_name_ref, 0, [
                        filter_text,
                        ], default_format=f_title)
                    sheet['row'] += 2

                # Print header
                excel_pool.write_xls_line(
                    ws_name_ref, sheet['row'], sheet['header'],
                    default_format=f_header
                    )
                sheet['row'] += 1

            # -----------------------------------------------------------------
            # A. STOCK MATERIAL:
            # -----------------------------------------------------------------
            if mask['Consegne'][0]:
                ws_name = 'Consegne'
                ws_name_ref = get_ws_name(ws_name, report_mode, multi)

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

                                    subtotal1 = \
                                        standard_price * move.product_qty
                                    subtotal2 = \
                                        discount_price * move.product_qty
                                    subtotal3 = \
                                        list_price * move.product_qty

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
                                        picking.account_id.name or
                                        'NON ASSEGNATA',
                                        picking.contact_id.name or '/',
                                        picking.name,
                                        formatLang(picking.min_date[:10]),
                                        pick_state_map.get(
                                            picking.pick_state, ''),

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
                                        ws_name_ref, sheet['row'], data,
                                        default_format=f_text_color
                                        )
                                    sheet['row'] += 1

                                    # -----------------------------------------
                                    #                    TOTALS:
                                    # -----------------------------------------
                                    # A. Total per account:
                                    # document_total += subtotal3
                                    total[account_id] += subtotal3

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
                                    ws_name_ref, sheet['row'], data,
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

                    # ---------------------------------------------------------
                    # Total line at the end of the block:
                    # ---------------------------------------------------------
                    excel_pool.write_xls_line(
                        ws_name_ref,
                        sheet['row'],
                        self.data_mask_filter([
                            (summary[ws_name]['total_cost'], f_number),
                            (summary[ws_name]['total_discount'], f_number),
                            (summary[ws_name]['total_revenue'], f_number),
                            ], mask['Consegne'][2]),
                        default_format=f_text,
                        col=mask['Consegne'][3])

            # -----------------------------------------------------------------
            # B. DDT MATERIAL:
            # -----------------------------------------------------------------
            if mask['DDT'][0]:
                ws_name = 'DDT'
                ws_name_ref = get_ws_name(ws_name, report_mode, multi)

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
                                        (product_name, list_price,
                                         standard_price, discount_price,
                                         discount_vat) = \
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
                                                ddt.delivery_date or
                                                ddt.date))[:10],

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
                                            ws_name_ref, sheet['row'], data,
                                            default_format=f_text_color,
                                            )
                                        sheet['row'] += 1

                                        # -------------------------------------
                                        #               TOTALS:
                                        # -------------------------------------
                                        # A. Total per account:
                                        total[account_id] += subtotal3  # XXX

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
                                            ddt.delivery_date or
                                            ddt.date))[:10],

                                        # Move:
                                        'NESSUN MOVIMENTO',
                                        '/',
                                        (0.0, f_number),
                                        (0.0, f_number),
                                        (0.0, f_number),
                                        ], mask['DDT'][1])

                                    excel_pool.write_xls_line(
                                        ws_name_ref, sheet['row'], data,
                                        default_format=f_text
                                        )
                                    sheet['row'] += 1
                        else:  # no
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
                                ws_name_ref, sheet['row'], data,
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

                # -------------------------------------------------------------
                # Total line at the end of the block:
                # -------------------------------------------------------------
                excel_pool.write_xls_line(
                    ws_name_ref,
                    sheet['row'],
                    self.data_mask_filter([
                        (summary[ws_name]['total_cost'], f_number),
                        (summary[ws_name]['total_discount'], f_number),
                        (summary[ws_name]['total_revenue'], f_number),
                        ], mask['DDT'][2]),
                    default_format=f_text, col=mask['DDT'][3])

            # -----------------------------------------------------------------
            # C. INVOICE:
            # -----------------------------------------------------------------
            if mask['Fatture'][0]:
                ws_name = 'Fatture'
                ws_name_ref = get_ws_name(ws_name, report_mode, multi)

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
                            ws_name_ref, sheet['row'], data,
                            default_format=f_text,
                            )
                        sheet['row'] += 1

                        # -----------------------------------------------------
                        #                    TOTALS:
                        # -----------------------------------------------------
                        # A. Total per account:
                        total[account_id] += subtotal3  # XXX

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

                # -------------------------------------------------------------
                # Total line at the end of the block:
                # -------------------------------------------------------------
                excel_pool.write_xls_line(
                    ws_name_ref,
                    sheet['row'],
                    self.data_mask_filter([
                        (summary[ws_name]['total_cost'], f_number),
                        (summary[ws_name]['total_discount'], f_number),
                        (summary[ws_name]['total_revenue'], f_number),
                        ], mask['Fatture'][2]),
                    default_format=f_text, col=mask['Fatture'][3])

            # -----------------------------------------------------------------
            # C. EXPENSE GROUPED BY:
            # -----------------------------------------------------------------
            if mask['Spese'][0]:
                ws_name = 'Spese'
                ws_name_ref = get_ws_name(ws_name, report_mode, multi)

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

                        if category.id not in total:  # todo
                            total[category.id] = 0.0

                        data = self.data_mask_filter([
                            formatLang(expence.date),
                            account.name or '',
                            category.name or '',
                            expence.name or '',
                            (subtotal1, f_number),
                            (subtotal2, f_number),
                            (subtotal3, f_number),
                            ], mask['Spese'][1])

                        excel_pool.write_xls_line(
                            ws_name_ref, sheet['row'], data,
                            default_format=f_text,
                            )
                        sheet['row'] += 1

                        # -----------------------------------------------------
                        # Summary data (expence):
                        # -----------------------------------------------------
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

                        # -----------------------------------------------------
                        #                    TOTALS:
                        # -----------------------------------------------------
                        # A. Total per account:
                        total[category.id] += subtotal1

                        # B. Line total in same sheet:
                        summary[ws_name]['total_cost'] += subtotal1
                        summary[ws_name]['total_discount'] += 0.0
                        summary[ws_name]['total_revenue'] += subtotal3

                # -------------------------------------------------------------
                # Total line at the end of the block:
                # -------------------------------------------------------------
                excel_pool.write_xls_line(
                    ws_name_ref,
                    sheet['row'],
                    self.data_mask_filter([
                        (summary[ws_name]['total_cost'], f_number),
                        (summary[ws_name]['total_discount'], f_number),
                        (summary[ws_name]['total_revenue'], f_number),
                        ], mask['Spese'][2]),
                    default_format=f_text,
                    col=mask['Spese'][3])

            # -----------------------------------------------------------------
            # D. MATERIAL GROUPED BY:
            # -----------------------------------------------------------------
            if mask['Materiali'][0]:
                ws_name = 'Materiali'
                ws_name_ref = get_ws_name(ws_name, report_mode, multi)

                sheet = sheets[ws_name]
                material_rows = {}

                # -------------------------------------------------------------
                # Read picking:
                # -------------------------------------------------------------
                for key in picking_db:
                    for picking in picking_db[key]:
                        if picking.move_lines:
                            if picking.move_lines:
                                for move in picking.move_lines:
                                    self.material_update(
                                        cr, uid, material_rows, move,
                                        context=context)

                # -------------------------------------------------------------
                # Read DDT:
                # -------------------------------------------------------------
                for key in ddt_db:
                    for ddt in ddt_db[key]:
                        if ddt.picking_ids:
                            for picking in ddt.picking_ids:
                                if picking.move_lines:
                                    for move in picking.move_lines:
                                        self.material_update(
                                            cr, uid, material_rows, move,
                                            context=context)

                # -------------------------------------------------------------
                # Excel page "Materiali": 1. Material
                # -------------------------------------------------------------
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
                        ws_name_ref, sheet['row'], data,
                        default_format=f_text,
                        )
                    sheet['row'] += 1

                # Total for block:
                data = self.data_mask_filter([
                    ('Totale', f_title), '', '', '', '', '', '',
                    sub1, sub2, sub3,
                    ], mask['Materiali'][1])
                excel_pool.write_xls_line(
                    ws_name_ref, sheet['row'], data,
                    default_format=f_number,
                    )
                excel_pool.merge_cell(ws_name_ref, [
                    # todo parametrize on header:
                    sheet['row'], 0, sheet['row'], 4,
                    ])

                # -------------------------------------------------------------
                # Excel page "Materiali": 2. Intervention
                # -------------------------------------------------------------
                sub_amount = sub_h = 0.0
                if intervent_db:
                    # Print header
                    sheet['row'] += 2
                    excel_pool.write_xls_line(
                        ws_name_ref, sheet['row'], [
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

                            # todo Jump invoiced?
                            if intervent.is_invoiced:
                                continue

                            # -------------------------------------------------
                            # Totals:
                            # -------------------------------------------------
                            sub_amount -= intervent.amount
                            sub_h += intervent.unit_amount

                        # -----------------------------------------------------
                        # Total line at the end of the block:
                        # -----------------------------------------------------
                        excel_pool.write_xls_line(
                            ws_name_ref, sheet['row'], [
                                'Interventi del periodo',
                                (sub_amount, f_number),
                                (sub_h, f_number),
                                ], default_format=f_text)

                # -------------------------------------------------------------
                # Excel page Materiali: 3. Expences
                # -------------------------------------------------------------
                subtotal1 = 0.0
                if expence_db:
                    # Print header
                    sheet['row'] += 2

                    excel_pool.write_xls_line(
                        ws_name_ref, sheet['row'], [
                            'Descrizione', 'Costo',
                            # 'Costo esposto',
                            ], default_format=f_header)

                    sheet['row'] += 1
                    for key in expence_db:
                        for expence in expence_db[key]:
                            subtotal1 += expence.total

                    # Total:
                    excel_pool.write_xls_line(
                        ws_name_ref, sheet['row'], [
                            'Spese extra',
                            (subtotal1, f_number),
                            ], default_format=f_text,
                        )

                # Total cost:
                sheet['row'] += 2
                excel_pool.write_xls_line(
                    ws_name_ref, sheet['row'], [
                        'Tot. costi materiali, interventi e spese extra: '
                        'EUR %s' % sum(
                            (sub1, subtotal1, sub_amount)),
                        ], default_format=f_title,
                    )
            # -----------------------------------------------------------------
            # E. INTERVENTION:
            # -----------------------------------------------------------------
            if mask['Interventi'][0]:  # Show / Hide page:
                ws_name = 'Interventi'
                ws_name_ref = get_ws_name(ws_name, report_mode, multi)

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
                        if user_mode_id in partner_forced:  # partner forced
                            unit_revenue = partner_forced[user_mode_id]
                        else:  # read for default list:
                            unit_revenue = mode_pricelist.get(
                                user_mode_id, 0.0)

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
                            (this_cost, f_number_color),  # total cost
                            (this_revenue, f_number_color),  # total revenue

                            intervent.to_invoice.name or '/',
                            'X' if intervent.not_in_report else '',

                            intervent.state,
                            'X' if intervent.is_invoiced else '',
                            ], mask['Interventi'][1])

                        excel_pool.write_xls_line(
                            ws_name_ref, sheet['row'], data,
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

                        # -----------------------------------------------------
                        # Totals:
                        # -----------------------------------------------------
                        # A. Total per account:
                        cost[account_id] += this_cost
                        total[account_id] += this_revenue

                        # B. Line total in same sheet:
                        summary[ws_name]['total_cost'] += this_cost
                        summary[ws_name]['total_revenue'] += this_revenue

                    # ---------------------------------------------------------
                    # Total line at the end of the block:
                    # ---------------------------------------------------------
                    excel_pool.write_xls_line(
                        ws_name_ref,
                        sheet['row'],
                        self.data_mask_filter([
                            (summary[ws_name]['total_cost'], f_number),
                            (summary[ws_name]['total_revenue'], f_number),
                            ], mask['Interventi'][2]),
                        default_format=f_text,
                        col=mask['Interventi'][3])

            # -----------------------------------------------------------------
            # F. ACCOUNT:
            # -----------------------------------------------------------------
            if mask['Commesse'][0]:
                ws_name = 'Commesse'
                ws_name_ref = get_ws_name(ws_name, report_mode, multi)

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
                            ws_name_ref, sheet['row'], data,
                            default_format=f_text
                            )
                        sheet['row'] += 1

                # Block account used:
                sheet['row'] += 2
                excel_pool.write_xls_line(
                    ws_name_ref, sheet['row'],
                    [u'Commesse toccate nel periodo:', ],
                    default_format=f_title
                    )

                sheet['row'] += 1
                excel_pool.write_xls_line(
                    ws_name_ref, sheet['row'], sheet['header'],
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
                        '/',  # account.fiscal_position.name,
                        account.total_hours,
                        account.state,
                        ], mask['Commesse'][1])

                    excel_pool.write_xls_line(
                        ws_name_ref, sheet['row'], data,
                        default_format=f_text
                        )
                    sheet['row'] += 1

            # -----------------------------------------------------------------
            #                           SUMMARY:
            # -----------------------------------------------------------------
            if mask['Riepilogo'][0]:
                ws_name = 'Riepilogo'
                ws_name_ref = get_ws_name(ws_name, report_mode, multi)

                sheet = sheets[ws_name]

                for block in sheet_order[1:-2]:  # Jump todo commesse?!?

                    # Check if sheet must be created:
                    if block in mask and not mask[block][0]:
                        continue

                    block_record = summary[block]
                    if not block_record['data']:
                        _logger.warning('No summary block %s' % block)
                        continue

                    excel_pool.write_xls_line(
                        ws_name_ref, sheet['row'], ['Blocco: %s' % block],
                        default_format=f_title
                        )
                    sheet['row'] += 1

                    excel_pool.write_xls_line(
                        ws_name_ref,
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
                                    ws_name_ref,
                                    sheet['row'],
                                    self.data_mask_filter(
                                        record, mask[block][4]),
                                    default_format=f_text,
                                    )
                                sheet['row'] += 1

                    # ---------------------------------------------------------
                    # Total line:
                    # ---------------------------------------------------------
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
                        ws_name_ref, sheet['row'], data, default_format=f_text,
                        col=mask[block][6])

                    sheet['row'] += 1

                # -------------------------------------------------------------
                # TOTAL BLOCK:
                # -------------------------------------------------------------
                # Header:
                sheet['row'] += 1
                excel_pool.write_xls_line(
                    ws_name_ref, sheet['row'], self.data_mask_filter([
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
                    # ---------------------------------------------------------
                    # Parameters:
                    # ---------------------------------------------------------
                    total_cost = summary[block].get('total_cost', 0.0)
                    total_discount = summary[block].get('total_discount', 0.0)
                    total_revenue = summary[block].get('total_revenue', 0.0)

                    if not any((total_cost, total_discount, total_revenue)):
                        continue

                    sheet['row'] += 1
                    excel_pool.write_xls_line(
                        ws_name_ref, sheet['row'],
                        self.data_mask_filter([
                            block,
                            (total_cost, f_number),
                            (total_discount, f_number),
                            (total_revenue, f_number),
                            ], mask['Total']), default_format=f_text)

                    # ---------------------------------------------------------
                    # Total
                    # ---------------------------------------------------------
                    total['total_cost'] += total_cost
                    total['total_discount'] += total_discount
                    total['total_revenue'] += total_revenue

                # Final total of the table:
                sheet['row'] += 1
                excel_pool.write_xls_line(
                    ws_name_ref, sheet['row'], self.data_mask_filter([
                        ('Totale:', f_title),
                        (total.get('total_cost', 0.0), f_number),
                        (total.get('total_discount', 0.0), f_number),
                        (total.get('total_revenue', 0.0), f_number),
                        ], mask['Total']), default_format=f_text)

            # -----------------------------------------------------------------
            #                            PRIVATE MODE:
            # -----------------------------------------------------------------
            # Custom setup (not as previous)
            if report_mode == 'private':
                ws_name = 'Ridotta'
                ws_name_ref = get_ws_name(ws_name, report_mode, multi)

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
                excel_pool.column_width(
                    ws_name_ref, [14, 30, 5, 14, 12, 12])

                # -------------------------------------------------------------
                # Insert Logo:
                logo_field = company.logo or company.partner_id.image
                data_image = excel_pool.clean_odoo_binary(logo_field)

                excel_pool.row_height(ws_name_ref, (row, ), height=65)
                excel_pool.write_image(
                    ws_name_ref, row, 0,
                    x_offset=0, y_offset=0,
                    x_scale=0.25, y_scale=0.25,
                    positioning=2,
                    filename=False,
                    data=data_image,
                    tip='Logo',
                    # url=False,
                )
                excel_pool.write_xls_line(ws_name_ref, row, [
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
                excel_pool.write_xls_line(ws_name_ref, row, [
                    ('Cliente', f_title),
                    u'%s' % partner.name,
                    ], default_format=f_title)
                row += 1
                excel_pool.write_xls_line(ws_name_ref, row, [
                    ('Indirizzo', f_title),
                    'Via %s - %s %s' % (
                        partner.street or '',
                        partner.zip or '',
                        partner.city or '',
                        )
                    ], default_format=f_title)

                row += 2
                # Filter text (merge cell):
                excel_pool.merge_cell(ws_name_ref, [row, 0, row, 5])
                excel_pool.write_xls_line(ws_name_ref, row, [
                    filter_text,
                    ], default_format=f_title)

                private_summary = []

                # -------------------------------------------------------------
                # A. STOCK MATERIAL:
                # -------------------------------------------------------------
                if any(picking_db.values()):
                    # Print header
                    row += 2
                    excel_pool.write_xls_line(
                        ws_name_ref, row, [
                            'MATERIALI', '', '', '', '', '',
                            ], default_format=f_header)

                    row += 1
                    excel_pool.write_xls_line(
                        ws_name_ref, row, [
                            'Codice', 'Descrizione', 'UM', 'Q.',
                            'Prezzo unitario', 'Totale',
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
                                    else:  # discount_vat
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
                                        ws_name_ref, row, data,
                                        default_format=f_text_color
                                        )
                                    # -----------------------------------------
                                    #                  TOTALS:
                                    # -----------------------------------------
                                    total += subtotal

                    # ---------------------------------------------------------
                    # Total line at the end of the block:
                    # ---------------------------------------------------------
                    row += 1
                    excel_pool.write_xls_line(
                        ws_name_ref, row, [(total, f_number)],
                        default_format=f_text, col=5)

                    # Discount if present:
                    if activity_material_discount:
                        row += 1
                        discount = total * (
                            100.0 - activity_material_discount) / 100.0
                        excel_pool.write_xls_line(
                            ws_name_ref, row, [
                                '- %s%% Sconto' % activity_material_discount,
                                (discount, f_number),
                                ], default_format=f_text,
                            col=4)
                        private_summary.append(('Consegne', discount))
                    else:
                        private_summary.append(('Consegne', total))

                # -------------------------------------------------------------
                # B. DDT MATERIAL:
                # -------------------------------------------------------------
                if any(ddt_db.values()):
                    # Print header
                    row += 2
                    excel_pool.write_xls_line(
                        ws_name_ref, row, [
                            'MATERIALI DDT', '', '', '', '', '',
                            ], default_format=f_header)

                    row += 1
                    excel_pool.write_xls_line(
                        ws_name_ref, row, [
                            'Codice', 'Descrizione', 'UM', 'Q.',
                            'Prezzo unitario', 'Totale',
                            ], default_format=f_header)

                    total = 0.0
                    for key in ddt_db:
                        for ddt in ddt_db[key]:
                            if ddt.picking_ids:
                                for picking in ddt.picking_ids:
                                    for move in picking.move_lines:
                                        # Extract data:
                                        product = move.product_id
                                        (product_name, list_price,
                                         standard_price,
                                         discount_price, discount_vat) = \
                                             product_pool.extract_product_data(
                                                 cr, uid, move,
                                                 context=context)

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
                                            ws_name_ref, row, data,
                                            default_format=f_text_color,
                                            )

                                        # -------------------------------------
                                        #                TOTALS:
                                        # -------------------------------------
                                        total += subtotal

                    # ---------------------------------------------------------
                    # Total line at the end of the block:
                    # ---------------------------------------------------------
                    row += 1
                    excel_pool.write_xls_line(
                        ws_name_ref, row, [(total, f_number)],
                        default_format=f_text, col=5)

                    # Discount if present:
                    if activity_material_discount:
                        row += 1
                        discount = total * (
                            100.0 - activity_material_discount) / 100.0
                        excel_pool.write_xls_line(
                            ws_name_ref, row, [
                                '- %s%% Sconto' % activity_material_discount,
                                (discount, f_number),
                                ], default_format=f_text,
                            col=4)
                        private_summary.append(('DDT', discount))
                    else:
                        private_summary.append(('DDT', total))

                # -------------------------------------------------------------
                # C. INTERVENTION:
                # -------------------------------------------------------------
                if any(intervent_db.values()):
                    partner_forced = False  # update first time!
                    total = 0.0

                    # Print header
                    row += 2
                    excel_pool.write_xls_line(
                        ws_name_ref, row, [
                            'MANODOPERA', '', '', '', '',
                            ], default_format=f_header)

                    row += 1
                    excel_pool.write_xls_line(
                        ws_name_ref, row, [
                            # 'Codice', 'Descrizione', 'UM', 'Q.',
                            # 'Prezzo unitario', 'Totale',
                            'Data', 'Intervento', 'H.', 'Utente',
                            'Prezzo totale',
                            ], default_format=f_header)

                    for key in intervent_db:
                        for intervent in intervent_db[key]:
                            # Readability:
                            user = intervent.user_id
                            partner = intervent.intervent_partner_id
                            user_mode_id = intervent.user_mode_id.id

                            # -------------------------------------------------
                            # Initial setup of mapping and forced price
                            # database:
                            # -------------------------------------------------
                            if partner_forced == False:
                                partner_forced = {}
                                for forced in partner.mode_revenue_ids:
                                    partner_forced[forced.mode_id.id] = \
                                        forced.list_price
                            # -------------------------------------------------
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
                                # intervent.intervent_duration
                                # intervent.unit_amount
                                # total revenue:
                                (this_revenue, f_number_color),
                                ]

                            row += 1
                            excel_pool.write_xls_line(
                                ws_name_ref, row, data,
                                default_format=f_text_color
                                )
                            total += this_revenue

                    # ---------------------------------------------------------
                    # Total line at the end of the block:
                    # ---------------------------------------------------------
                    row += 1
                    excel_pool.write_xls_line(
                        ws_name_ref, row, [
                            (total, f_number),
                            ],
                        default_format=f_text, col=4)
                    private_summary.append(('Interventi', total))

                # -------------------------------------------------------------
                # SUMMARY:
                # -------------------------------------------------------------
                total = 0.0

                # Print header
                row += 2
                excel_pool.write_xls_line(
                    ws_name_ref, row, [
                        'Blocco', 'Totale',
                        ], default_format=f_header)

                for block, subtotal in private_summary:
                    row += 1
                    total += subtotal
                    excel_pool.write_xls_line(
                        ws_name_ref, row, [
                            block,
                            (subtotal, f_number),
                            ], default_format=f_text)
                row += 1
                excel_pool.write_xls_line(
                    ws_name_ref, row, [
                        total,
                        ], default_format=f_number, col=1)

        if save_fullname:
            _logger.info('Save as file: %s' % save_fullname)
            excel_pool.save_file_as(save_fullname)
            pdb.set_trace()
            return summary
        else:
            _logger.info('Return as report')
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
            ('complete', 'Completa (Interna, Cliente (Dett., Riep., Word)'),

            # User report:
            ('user', u'Attività Tecnici'),
            ('timesheet', u'Foglio presenze'),
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
        'float_time': fields.boolean(
            'Formatted hour',
            help='If checked print hour in HH:MM format'),

        # Picking management:
        'picking_mode': fields.selection([
            ('todo', 'Da consegnare'),
            ('delivered', 'Consegnati'),
            ('all', 'Tutti'),
            ], 'Modo picking', required=True,
            help='Indica quali documenti di consegna materiale considerare'
                 'nella stampa.'),

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
        'picking_mode': lambda *x: 'all',
        'ddt_mode': lambda *x: 'ddt',
        'intervent_mode': lambda *x: 'pending',
        }

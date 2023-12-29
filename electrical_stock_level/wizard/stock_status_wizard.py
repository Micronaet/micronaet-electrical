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
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)


class ProductProductStockStatusWizard(orm.TransientModel):
    """ Wizard for product stock status
    """
    _name = 'product.product.stock.status.wizard'

    def action_print(self, cr, uid, ids, context=None):
        """ Print report event
        """
        metel_state = {
            '1': 'Nuovo prodotto',
            '2': 'Finito o cancellato',
            '3': 'Gestito a magazzino',
            '4': 'Nuovo servizio',
            '5': 'Servizio cancellato',
            '6': 'Prodotto su ordinato',
            '7': 'Prodotto su ordinato (da cancellare)',
            '8': 'Servizio (no materiale)',
            '9': 'Cancellato',
        }
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]

        mode = wiz_browse.mode
        filter_mode = wiz_browse.filter
        start_code = wiz_browse.start_code
        moved_date = wiz_browse.moved_date

        # ---------------------------------------------------------------------
        # Pool used:
        # ---------------------------------------------------------------------
        excel_pool = self.pool.get('excel.writer')
        move_pool = self.pool.get('stock.move')
        location_pool = self.pool.get('stock.location')
        product_pool = self.pool.get('product.product')

        # ---------------------------------------------------------------------
        # Load stock location:
        # ---------------------------------------------------------------------
        location_used = {}
        location_ids = location_pool.search(cr, uid, [
            ('active', '=', True),
            ('usage', '!=', 'view'),
        ], context=context)
        for location in location_pool.browse(
                cr, uid, location_ids, context=context):
            location_used[location.name.lower()] = location.id

        # ---------------------------------------------------------------------
        # Product filter:
        # ---------------------------------------------------------------------
        domain = []

        moved_qty = {}
        # log_f = open('/tmp/move.log.csv')
        if moved_date:
            move_ids = move_pool.search(cr, uid, [
                ('date', '>=', '%s 00:00:00' % moved_date),
                ('state', '=', 'done'),
            ], context=context)
            move_proxy = move_pool.browse(cr, uid, move_ids, context=context)
            for move in move_proxy:
                product_id = move.product_id.id
                date = str(move.date)[:10]  # Only date
                price = move.price_unit
                quantity = move.product_qty

                if product_id not in moved_qty:
                    # Q., last price, last date
                    moved_qty[product_id] = [
                        0.0,  # Q. (in and out)
                        0.0,  # Last price
                        '',  # Last date
                        0.0,  # Q. out
                        0.0,  # Value out
                    ]

                if move.location_dest_id.id == location_used['stock']:  # IN
                    moved_qty[product_id][0] += quantity

                    # Manage last price:
                    if date > moved_qty[product_id][2] and price:
                        moved_qty[product_id][1] = price
                        moved_qty[product_id][2] = date

                    # Total data:
                    moved_qty[product_id][3] += quantity
                    moved_qty[product_id][4] += quantity * price

                else:  # OUT
                    moved_qty[product_id][0] -= move.product_qty

            domain.append(('id', 'in', moved_qty.keys()))

            # date_expected
            # (warehouse_id, inventory_id, invoice_state)

        if start_code:
            domain.append(('default_code', '=ilike', '%s%%' % start_code))

        if filter_mode == 'positive':
            domain.append(('qty_available', '>', 0))
        elif filter_mode == 'negative':
            domain.append(('qty_available', '<', 0))
        elif filter_mode == 'zero':
            domain.append(('qty_available', '=', 0))

        product_ids = product_pool.search(cr, uid, domain, context=context)
        product_proxy = product_pool.browse(
            cr, uid, product_ids, context=context)
        _logger.info('Selected products # %s for report' % len(product_ids))

        # ---------------------------------------------------------------------
        #                         Excel report:
        # ---------------------------------------------------------------------
        # Partner:
        ws_name = 'Stato magazzino'
        row = 0
        header = [
            'Codice', 'Nome',

            'Produttore', 'Marchio', 'Ultima var.',
            'Q.x pack', 'Stato',
            # 'Electrocod', 'Categoria',

            'UM', 'Da movim.', 'Magazzino',
            'Ultimo prezzo', 'Prezzo medio',
            'Valore all\'ultimo', 'Valore al medio',
            ]
        width = [
            12, 40,
            15, 15, 12,
            6, 15,
            # 10, 15,
            5, 10, 10,
            12, 12,
            13, 13,
        ]
        excel_pool.create_worksheet(ws_name)
        excel_pool.freeze_panes(ws_name, 1, 2)

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
        excel_pool.column_width(ws_name, width)

        # Print header
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=excel_format['header'])
        row += 1

        for product in product_proxy:
            product_id = product.id
            qty_available = product.qty_available

            if qty_available < 0.0:
                color_format = excel_format['red']
            else:
                color_format = excel_format['white']

            stock_qty, last_price, last_date, q_out, value_out = \
                moved_qty[product_id]
            if q_out:
                medium_price = value_out / q_out
            else:
                medium_price = 0.0

            if qty_available > 0:
                stock_value = qty_available * last_price
                stock_value_medium = qty_available * medium_price
            else:  # If not q. no total
                stock_value = stock_value_medium = 0.0

            data = [
                product.default_code,
                product.name,

                product.metel_producer_id.name or '',
                product.metel_brand_id.name or '',
                product.metel_last_variation or '',
                product.metel_q_x_pack or '',
                metel_state.get(product.metel_state, ''),
                # product.metel_electrocod or '',
                # product.categ_id.name or '',

                product.uom_id.name,
                (stock_qty, color_format['number']),
                (qty_available, color_format['number']),

                (last_price, color_format['number']),
                (medium_price, color_format['number']),

                (stock_value, color_format['number']),
                (stock_value_medium, color_format['number']),

                ]

            excel_pool.write_xls_line(
                ws_name, row, data,
                default_format=color_format['text']
                )
            row += 1

        return excel_pool.return_attachment(cr, uid, 'stock_status_report')

    _columns = {
        'mode': fields.selection([
            # Internal:
            ('stock', 'Stato magazzino'),
            ], 'Modalità', required=True),

        'start_code': fields.char('Inizio codice', size=20),
        'moved_date': fields.date('Movimentato da'),
        # 'from_date': fields.date('From date >= ', required=True),
        # 'to_date': fields.date('To date <=', required=True),
        'filter': fields.selection([
            ('all', 'Tutti'),
            ('positive', 'Con magazzino'),
            ('zero', 'Senza esistenza'),
            ('negative', 'Negativi'),
            ], 'Filtro', required=True),
        'float_time': fields.boolean(
            'Ora formattata',
            help='Se spuntato rappresenta gli orari in HH:MM, '
                 'diversamente in numero reale permettendo le somme.'),
        }

    _defaults = {
        'mode': lambda *x: 'stock',
        'filter': lambda *x: 'all',
        'float_time': lambda *x: True,
        }

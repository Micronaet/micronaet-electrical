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
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]

        mode = wiz_browse.mode
        filter_mode = wiz_browse.filter
        start_code = wiz_browse.start_code
        # from_date = wiz_browse.from_date
        # to_date = wiz_browse.to_date

        # ---------------------------------------------------------------------
        # Pool used:
        # ---------------------------------------------------------------------
        excel_pool = self.pool.get('excel.writer')

        move_pool = self.pool.get('stock.move')
        product_pool = self.pool.get('product.product')

        # ---------------------------------------------------------------------
        # A. Picking partner:
        # ---------------------------------------------------------------------
        domain = [
            # ('min_date', '>=', '%s 00:00:00' % from_date),
            # ('min_date', '<=', '%s 23:59:59' % to_date),
            ]

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
            'Q. x pack', 'Stato',
            # 'Electrocod',
            'Categoria',

            'UM', 'Stato',
            ]
        width = [
            10, 40,
            15, 15, 12,
            5, 10,
            # 10,
            15,
            5, 10,
        ]

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

        for product in product_proxy:
            data = [
                product.default_code,
                product.name,

                product.metel_producer_id.name or '',
                product.metel_brand_id.name or '',
                product.metel_last_variation or '',
                product.metel_q_x_pack or '',
                product.metel_state or '',
                # product.metel_electrocod or '',
                product.categ_id.name or '',

                product.uom_id.name,
                (product.qty_available, f_number),
                ]

            excel_pool.write_xls_line(
                ws_name, row, data,
                default_format=f_text
                )
            row += 1

        return excel_pool.return_attachment(cr, uid, 'stock_status_report')

    _columns = {
        'mode': fields.selection([
            # Internal:
            ('stock', 'Stato magazzino'),
            ], 'Modalità', required=True),

        'start_code': fields.char('Inizio codice', size=20),
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
        'filter': lambda *x: 'positive',
        'float_time': lambda *x: True,
        }

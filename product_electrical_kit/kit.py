# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
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

class ProductProductKit(orm.Model):
    """ Model name: ProductProductKit
    """
    _name = 'product.product.kit'
    _description = 'Product Kit'
    _rec_name = 'product_id'
    _order = 'product_id'

    def onchange_categ_id(self, cr, uid, ids, categ_id, context=None):
        """ Force product domain filter in present
        """
        res = {}
        res['domain'] = {
            'component_id': []
            }
        if categ_id:
            res['domain']['component_id'].extend([
                #('product_id', '!=', ids[0]), # TODO
                ('metel_serie_id', '=', categ_id),
                ])
        return res

    _columns = {
        'product_id': fields.many2one('product.product', 'Product'),
        'component_id': fields.many2one(
            'product.product', 'Component', required=True),
        'qty': fields.integer('Q.ty', required=True),
        'categ_id': fields.many2one(
            'product.category', 'Category brand',
            help='Category managed as productor brand'),
        }

    _defaults = {
        'qty': lambda *x: 1,
        }

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """

    _inherit = 'product.product'

    def get_kit_price_serie(self, cr, uid, product_id, serie_id, context=None):
        """ Get product price from serie passed:
        """
        res = 0.0
        component_ids = self.browse(
            cr, uid, product_id, context=context).component_ids
        for cmpt in component_ids:
            cmpt_serie_id = cmpt.metel_serie_id.id
            if not cmpt_serie_id or cmpt_serie_id != serie_id:
                res += cmpt.qty * cmpt.lst_price # TODO use pricelist
        return res

    def extract_check_report_xlsx(self, cr, uid, ids, context=None):
        """ Report for check kit definition
        """
        # Pool used:
        excel_pool = self.pool.get('excel.writer')

        # ---------------------------------------------------------------------
        # Collect data:
        # ---------------------------------------------------------------------
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        brand_db = {}  # NOTE: False >> common part
        title = []
        col_width = [
            5, # qty
            13, # code
            35, # name
            8, # price
            1 # space
            ]
        col_common = len(col_width)

        for line in current_proxy.component_ids:
            brand = line.categ_id.name or False
            if brand in brand_db:
                brand_db[brand].append(line)
            else:
                brand_db[brand] = [line]
                if brand: # False >> Common
                    title.extend(col_width)

        # ---------------------------------------------------------------------
        #                            Generate XLS file:
        # ---------------------------------------------------------------------
        ws_name = _('KIT Check')
        excel_pool.create_worksheet(name=ws_name)
        excel_pool.column_width(ws_name, title)

        # ---------------------------------------------------------------------
        # Title
        # ---------------------------------------------------------------------
        row = 0
        # TODO title:
        excel_pool.write_xls_line(ws_name, row, [
            'Kit:',
            '[%s] %s' % (
                current_proxy.name,
                current_proxy.default_code or '/',
                )
            ])

        # ---------------------------------------------------------------------
        # Write header
        # ---------------------------------------------------------------------
        row = 1
        title_brand = []
        title_name = []
        for t in sorted(brand_db):
            if not t:
                continue
            title_brand.extend(['', '', t, '', ''])
            title_name.extend([
                _('Q.'),
                _('Code'),
                _('Name'),
                _('Price'),
                '',
                ])
        excel_pool.write_xls_line(ws_name, row, title_brand)
        row += 1
        excel_pool.write_xls_line(ws_name, row, title_name)

        # ---------------------------------------------------------------------
        # Write common block (no brand)
        # ---------------------------------------------------------------------
        # 1. Write common line:
        for line in brand_db.get(False, []):
            row += 1
            data = []
            for i in range(0, len(brand_db) - 1):
                data.extend([
                    line.qty,
                    line.component_id.default_code,
                    line.component_id.name,
                    line.component_id.lst_price,
                    '',
                    ])
            excel_pool.write_xls_line(ws_name, row, data)
        start = row # For next brand block

        # TODO 2. Write brand line:
        col = 0
        for brand in sorted(brand_db):
            if not brand:
                continue # jump common block

            row = start
            for line in sorted(
                    brand_db[brand],
                    key=lambda x: x.product_id.default_code):
                row += 1
                data = [
                    line.qty,
                    line.component_id.default_code,
                    line.component_id.name,
                    line.component_id.lst_price,
                    '',
                    ]
                excel_pool.write_xls_line(ws_name, row, data, col=col)
            col += col_common # Start position

        return excel_pool.return_attachment(
            cr, uid, name='KIT Check', name_of_file='kit_check.xlsx')

    def _check_kit_variant(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for item in self.browse(cr, uid, ids, context=context):
            res[item.id] = ''
            check_tot = item.kit_variant
            if not check_tot:
                continue
            groups = {}
            for cmpt in item.component_ids:
                categ_id = cmpt.categ_id
                if not categ_id:
                    continue
                if categ_id in groups:
                    groups[categ_id] += 1
                else:
                    groups[categ_id] = 1

            for group, tot in groups.iteritems():
                if tot != check_tot:
                    res[item.id] += '%s [%s]\n' % (group.name, tot)
        return res

    _columns = {
        'kit': fields.boolean('Kit'),
        'kit_variant': fields.integer('Kit variant',
            help='Kit number of supplier variant'),
        'kit_variant_check': fields.function(
            _check_kit_variant, method=True,
            type='text', string='Check variant', store=False),
        'component_ids': fields.one2many(
            'product.product.kit', 'product_id', 'Component'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

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
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)


_logger = logging.getLogger(__name__)


class ElectricalProductKit(orm.Model):
    """ Model name: electrical Product Kit
    """

    _name = 'electrical.product.kit'
    _description = 'Electrical Kit'
    _rec_name = 'name'
    _order = 'name'

    _columns = {
        'active': fields.boolean('Attiva'),
        'name': fields.char('Nome', size=80, required=True),
        'note': fields.text('Note'),
        }

    _defaults = {
        'active': lambda *x: True,
    }


class ProductProductKitLine(orm.Model):
    """ Model name: Product Kit
    """

    _name = 'electrical.product.kit.line'
    _description = 'Eletrical Kit line'
    _rec_name = 'product_id'
    _order = 'sequence'

    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        """ Force domain of product
        """
        product_pool = self.pool.get('product.product')
        res = {}
        if not product_id:
            return res

        product = product_pool.browse(cr, uid, product_id, context=context)
        res['value'] = {
            'uom_id': product.uom_id.id,
        }
        return res

    def onchange_search_code(self, cr, uid, ids, search_code, context=None):
        """ Force domain of product
        """
        res = {
            'domain': {'product_id': []},
            'value': {},
            }

        if search_code:
            res['domain']['product_id'].append(
                ('default_code', 'ilike', search_code))
        return res

    _columns = {
        'sequence': fields.integer('Seq.'),
        'search_code': fields.char('Cerca codice', size=40),
        'kit_id': fields.many2one(
            'electrical.product.kit', 'Kit'),
        'product_id': fields.many2one(
            'product.product', 'Componente', required=True),
        'uom_id': fields.many2one(
            'product.uom', 'UM', required=True),
        'quantity': fields.float('Q.', digits=(16, 2), required=True),
        }

    _defaults = {
        'sequence': lambda *x: 10,
        'quantity': lambda *x: 1,
    }


class StockPicking(orm.Model):
    """ Model name: Stock Picking
    """

    _inherit = 'stock.picking'

    def action_load_kit_item(self, cr, uid, ids, context=None):
        """ Open Kit wizard from Picking
        """
        if context is None:
            context = {}
        ctx = context.copy()

        # Setup context:
        ctx['default_picking_id'] = ids[0]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Carica Kit'),
            'view_type': 'form',
            'view_mode': 'form',
            # 'res_id': False,
            'res_model': 'load.electrical.product.kit.wizard',
            # 'view_id': view_id, # False
            'views': [(False, 'form')],
            'domain': [],
            'context': ctx,
            'target': 'new',  # 'new'
            'nodestroy': False,
        }


class ElectricalProductKitInherit(orm.Model):
    """ Model name: electrical Product Kit
    """

    _inherit = 'electrical.product.kit'

    _columns = {
        'product_ids': fields.one2many(
            'electrical.product.kit.line', 'kit_id', 'Componenti'),
        }


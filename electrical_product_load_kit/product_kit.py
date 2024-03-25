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
        'name': fields.char('Description', size=80, required=True),
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

    _columns = {
        'sequence': fields.integer('Seq.'),
        'search_code': fields.char('Cerca codice', size=40),
        'kit_id': fields.many2one(
            'electrical.product.kit', 'Kit'),
        'product_id': fields.many2one(
            'product.product', 'Componente', required=True),
        'uom_id': fields.many2one(
            'product.uom', 'UM', required=True),
        'quantity': fields.float('Q.', digits=(16, 2)),
        }

    _defaults = {
        'sequence': lambda *x: 10,
    }


class ElectricalProductKitInherit(orm.Model):
    """ Model name: electrical Product Kit
    """

    _inherit = 'electrical.product.kit'

    _columns = {
        'product_ids': fields.one2many(
            'electrical.product.kit.line', 'kit_id', 'Componenti'),
        }


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


class ProductProduct(orm.Model):
    """ Model name: Product product
    """

    _inherit = 'product.product'

    _columns = {
        'is_generic': fields.boolean('Generico'),
        }


class ResPartner(orm.Model):
    """ Model name: ResPartner
    """

    _inherit = 'res.partner'

    _columns = {
        'activity_material_discount': fields.float(
            'Material discount (report activity)', digits=(16, 4)),
        'activity_price': fields.selection([
            ('metel_sale', 'Discount price'),
            ('lst_price', 'List price'),
            ], 'Price used (report activity'),
        }

    _defaults = {
        'activity_price': lambda *x: 'lst_price',
        }


class AccountAnalyticAccount(orm.Model):
    """ Model name: Account
    """

    _inherit = 'account.analytic.account'

    _columns = {
        'activity_material_discount': fields.float(
            'Sconto materiale (report attività)', digits=(16, 4)),
        'activity_price': fields.selection([
            ('metel_sale', 'Prezzo scontato'),
            ('lst_price', 'Prezzo METEL (listino)'),
            ], 'Prezzo utilizzato (report attitivà)'),
        }

    _defaults = {
        # 'activity_price': lambda *x: 'lst_price',
        }

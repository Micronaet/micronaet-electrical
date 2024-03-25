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


class LoadProductKitWizard(orm.TransientModel):
    """ Wizard load component
    """
    _name = 'load.product.kit.wizard'

    def load_component(self, cr, uid, ids, context=None):
        """ Update generator with component data
        """
        line_pool = self.pool.get('sale.order.line')
        move_pool = self.pool.get('stock.move')

        if not context:
            context = {}
        wizard = self.browse(cr, uid, ids, context=context)

        order = wizard.order_id
        picking = wizard.picking_id
        kit = wizard.kit_id
        quantity = wizard.quantity

        # Generate line with kit:

    def onchange_kit_quantity(
            self, cr, uid, ids, kit_id, quantity, context=None):
        """ Generate a preview form
        """
        kit_pool = self.pool.get('product.product.kit')

        res = {}
        return res

    _columns = {
        'order_id': fields.many2one('sale.order', 'Ordine'),
        'picking_id': fields.many2one('stock.picking', 'Picking'),
        'kit_id': fields.many2one('product.product.kit', 'Kit', required=True),
        'quantity': fields.integer('Q.', required=True),
        }

    _defaults = {
        'quantity': lambda *x: 1,
        }

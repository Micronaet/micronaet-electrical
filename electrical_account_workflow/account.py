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


class AccountAnaliticAccount(orm.Model):
    """ Model name: Account Analitic Account
    """

    _inherit = 'account.analytic.account'

    # -------------------------------------------------------------------------
    # Workflow new actions:
    # -------------------------------------------------------------------------
    def set_invoicing(self, cr, uid, ids, context=None):
        """ Workflow invoicing
        """
        return self.write(cr, uid, ids, {
            'state': 'invoicing',
            }, context=context)

    def set_done(self, cr, uid, ids, context=None):
        """ Workflow done
        """
        return self.write(cr, uid, ids, {
            'state': 'done',
            }, context=context)

    _columns = {
        # Override state:
        'state': fields.selection([
            ('template', 'Modello'),
            ('draft', 'Bozza'),  # Not used
            ('open', 'In Corso'),  # First state
            ('pending', 'Sospeso'),
            ('close', 'Chiuso'),

            ('invoicing', 'Da fatturare'),
            ('done', 'Archiviato'),  # Last state

            ('cancelled', 'Cancellato')
        ], 'Stato', required=True, track_visibility='onchange', copy=False),
    }

    _defaults = {
        'state': 'open',
    }

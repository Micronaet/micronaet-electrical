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


class AccountAnaliticExpenceCategory(orm.Model):
    """ Model name: AccountAnaliticExpence
    """

    _name = 'account.analytic.expence.category'
    _description = 'Analytic expence category'
    _rec_name = 'name'
    _order = 'name'

    _columns = {
        'name': fields.char('Description', size=64, required=True),
        'note': fields.text('Note'),
        }


class AccountAnaliticExpence(orm.Model):
    """ Model name: Account Analitic Expence
    """

    _name = 'account.analytic.expence'
    _description = 'Analytic expence'
    _rec_name = 'name'
    _order = 'date'

    _columns = {
        'account_id': fields.many2one('account.analytic.account', 'Account'),
        'date': fields.date('Date', required=True),
        'category_id': fields.many2one(
            'account.analytic.expence.category', 'Category', required=True),
        'name': fields.char('Description', size=64, required=True),
        'total': fields.float('Total', digits=(16, 2), required=True),
        'total_forced': fields.float('Total forced', digits=(16, 2),
            help='If present is used instead of total value (as a revenue)'),
        'printable': fields.selection([
            ('always', 'Always'),
            ('conditional', 'Conditional (wizard selection)'),
            ('never', 'Never'),
            ], 'Printable', required=True),
        }

    _defaults = {
        'date': lambda *x: datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        'printable': lambda *x: 'always',
        }


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

    def open_expences_list(self, cr, uid, ids, context=None):
        """ Return list of expences:
        """
        return {
            'type': 'ir.actions.act_window',
            'name': _('Expence list'),
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'account.analytic.expence',
            'view_id': False,
            'views': [(False, 'tree')],
            'domain': [('account_id', '=', ids[0])],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }

    _columns = {
        'account_note': fields.text('Annotazioni'),
        'expence_ids': fields.one2many(
            'account.analytic.expence', 'account_id', 'Expence'),

        # Override state:
        'state': fields.selection([
            ('template', 'Template'),
            ('draft', 'Bozza'),  # Not used
            ('open', 'In Corso'),  # First state
            ('pending', 'Sospeso'),
            ('close', 'Chiusa'),

            ('invoicing', 'Da fatturare'),
            ('done', 'Archiviata'),  # Last state

            ('cancelled', 'Cancellata')
        ], 'Stato', required=True, track_visibility='onchange', copy=False),
    }

    _defaults = {
        'state': 'open',
    }

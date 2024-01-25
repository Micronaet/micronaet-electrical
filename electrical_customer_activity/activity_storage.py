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


class ResPartnerActivityStorageStage(orm.Model):
    """ Model name: Res Partner Activity Storage
    """

    _name = 'res.partner.activity.storage.stage'
    _description = 'Activity storage stage'
    _order = 'name'

    _columns = {
        'name': fields.char('Nome'),
        'note': fields.text('Note'),
        }


class ResPartnerActivityStorage(orm.Model):
    """ Model name: Res Partner Activity Storage
    """

    _name = 'res.partner.activity.storage'
    _description = 'Activity storage'
    _order = 'name desc, partner_id, account_id'

    # Button to open list:
    def get_total_intervent_draft(self, cr, uid, ids, context=None):
        """ Open Intervent not invoiced
        """
        if context is None:
            context = {}

        model_pool = self.pool.get('ir.model.data')
        intervent_pool = self.pool.get('hr.analytic.timesheet')

        store = self.browse(cr, uid, ids, context=context)[0]
        domain = [
            ('date_start', '>=', store.from_date),
            ('date_start', '<=', store.to_date),
            ('intervent_partner_id', '=', store.partner_id.id),
            ('intervent_contact_id', '=', store.contact_id.id),
            ('account_id', '=', store.account_id.id),
            ]
        if context.get('is_invoiced'):
            domain.append(('is_invoiced', '=', True))
            name = 'Interventi fatturati'
        else:
            domain.append(('is_invoiced', '=', False))
            name = 'Interventi da fatture'

        record_ids = intervent_pool.search(cr, uid, domain, context=context)
        tree_view_id = model_pool.get_object_reference(
            cr, uid,
            'intervention_repor',
            'view_hr_analytic_timesheet_tree',
            )[1]

        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'view_type': 'form',
            'view_mode': 'tree,form',
            # 'res_id': ids[0],
            'res_model': 'hr.analytic.timesheet',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (False, 'form')],
            'domain': [('id', 'in', record_ids)],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    def get_total_intervent_invoice(self, cr, uid, ids, context=None):
        """ Open Intervent invoiced
        """
        if context is None:
            context = {}

        context['is_invoiced'] = True

        return self.get_total_intervent_invoice(cr, uid, ids, context=context)

    def get_total_picking(self, cr, uid, ids, context=None):
        """ Open Picking
        """
        store = self.browse(cr, uid, ids, context=context)[0]

        picking_pool = self.pool.get('stock.picking')
        return True

    def get_total_ddt_draft(self, cr, uid, ids, context=None):
        """ Open DDT not invoiced
        """
        store = self.browse(cr, uid, ids, context=context)[0]

        ddt_pool = self.pool.get('stock.ddt')
        return True

    def get_total_ddt_invoice(self, cr, uid, ids, context=None):
        """ Open DDT invoiced
        """
        store = self.browse(cr, uid, ids, context=context)[0]

        ddt_pool = self.pool.get('stock.ddt')
        return True

    def get_total_invoice(self, cr, uid, ids, context=None):
        """ Open Invoice
        """
        store = self.browse(cr, uid, ids, context=context)[0]

        invoice_pool = self.pool.get('account.invoice')
        return True

    _columns = {
        'name': fields.char('Mese', size=8, required=True),
        'note': fields.text('Note'),
        'from_date': fields.date('Dalla data'),
        'to_date': fields.date('Alla data'),

        'partner_id': fields.many2one('res.partner', 'Cliente'),
        'contact_id': fields.many2one('res.partner', 'Contatto'),
        'account_id': fields.many2one(
            'account.analytic.account', 'Commessa'),
        'stage_id': fields.many2one(
            'res.partner.activity.storage.stage', 'Stato'),

        # Check:
        # 'check_intervent': fields.boolean('Interventi'),
        # 'check_stock': fields.boolean('Consegne'),
        # 'check_ddt': fields.boolean('DDT'),
        # 'check_invoice': fields.boolean('Fatture'),

        # Detail:
        'total_intervent_draft': fields.integer('# Int. da fatt.'),
        'total_intervent_invoice': fields.integer('# Int. fatt.'),
        'total_picking': fields.integer('# Pick. da fatt.'),
        'total_ddt_draft': fields.integer('# DDT da fatt.'),
        'total_ddt_invoice': fields.integer('# DDT fatt.'),
        'total_invoice': fields.integer('# Fatture'),

        # Amount:
        'amount_intervent': fields.float('Tot. Interventi', digits=(16, 2)),
        'amount_picking': fields.float('Tot. Consegnato', digits=(16, 2)),
        'amount_ddt': fields.float('Tot. DDT', digits=(16, 2)),
        'amount_invoice': fields.float('Tot. Fatturato', digits=(16, 2)),
        }



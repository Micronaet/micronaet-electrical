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



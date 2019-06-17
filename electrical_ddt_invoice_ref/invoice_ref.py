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

class ManualAccountInvoice(orm.Model):
    """ Model name: ManualAccountInvoice
    """
    
    _name = 'manual.account.invoice'
    _description = 'Manual invoice'
    _rec_name = 'name'
    _order = 'name'
    
    _columns = {
        'date': fields.date('Date', required=True),
        'name': fields.char(
            'Name', size=64, required=True, 
            ),
        'partner_id': fields.many2one('res.partner', 'Partner', required=True),    
        'account_id': fields.many2one('account.analytic.account', 'Account'),
        'contact_id': fields.many2one('res.partner', 'Contact'),
        'address_id': fields.many2one('res.partner', 'Address'),
        'total': fields.float('Total', digits=(16, 2)),
        }
    
    _defaults = {
        'date': lambda *x: datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        }    
        
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Name of invoice must be unique!'),        
        ]

class StockDDT(orm.Model):
    """ Model name: StockDDT
    """
    
    _inherit = 'stock.ddt'
    
    _columns = {
        'manual_invoice_id': fields.many2one(
            'manual.account.invoice', 'Invoice'),
        }

class ManualAccountInvoice(orm.Model):
    """ Model name: ManualAccountInvoice
    """
    
    _inherit = 'manual.account.invoice'

    _columns = {
        'ddt_ids': fields.one2many('stock.ddt', 'manual_invoice_id', 'DDT'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

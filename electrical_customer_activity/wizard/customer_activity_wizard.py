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
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)


class ResPartnerActivityWizard(orm.TransientModel):
    ''' Wizard for partner activity
    '''
    _name = 'res.partner.activity.wizard'

    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------
    def action_print(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        

        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        partner_id = self.partner_id.id # Mandatory:
        account_id = self.account_id.id
        from_date = self.from_date
        to_date = self.to_date

        # ---------------------------------------------------------------------
        # Pool used:
        # ---------------------------------------------------------------------
        excel_pool = self.pool.get('excel.writer')
        
        # Account:
        picking_pool = self.pool.get('stock.picking')
        ddt_pool = self.pool.get('stock.ddt')
        invoice_pool = self.pool.get('account.invoice')
        
        # ---------------------------------------------------------------------
        #                          STOCK MATERIAL:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('partner_id', '=', partner_id)
            ('min_date', '>=', '%s 00:00:00' % from_date)
            ('min_date', '<=', '%s 23:59:59' % to_date)
            ('ddt_id', '=', False), # Not DDT
            ]
        if account_id:
            domain.append(('account_id', '=', account_id))
        picking_ids = picking_pool.search(cr, uid, domain, context=context)
        picking_proxy = picking_pool.browse(
            cr, uid, picking_ids, context=context)
        picking_db = {}
        for picking in picking_proxy:
            key = (
                picking.pick_state, 
                #picking.partner_id.name,
                picking.account_id.name,
                )
            if key not in picking_db:
                picking_db[key] = []
            picking_db[key].append(picking)

        # ---------------------------------------------------------------------
        #                           DDT MATERIAL:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('partner_id', '=', partner_id)
            ('delivery_date', '>=', '%s 00:00:00' % from_date)
            ('delivery_date', '<=', '%s 23:59:59' % to_date)
            ('invoice_id', '=', False), # Not Invoiced
            ]
        if account_id:
            domain.append(('account_id', '=', account_id))
        ddt_ids = ddt_pool.search(cr, uid, domain, context=context)
        ddt_proxy = ddt_pool.browse(
            cr, uid, ddt_ids, context=context)
        ddt_db = {}
        for ddt in ddt_proxy:
            key = (
                #ddt.partner_id.name,
                ddt.account_id.name,
                ddt.name,
                )
            if key not in ddt_db:
                ddt_db[key] = []
            ddt_db[key].append(ddt)

        # ---------------------------------------------------------------------
        #                          INVOICED MATERIAL:
        # ---------------------------------------------------------------------
        # Domain:
        domain = [
            ('partner_id', '=', partner_id)
            ('date_invoice', '>=', from_date)
            ('date_invoice', '<=', to_date)
            ]
        if account_id:
            domain.append(('account_id', '=', account_id))
        invoice_ids = invoice_pool.search(cr, uid, domain, context=context)
        invoice_proxy = invoice_pool.browse(
            cr, uid, invoice_ids, context=context)
        invoice_db = {}
        for invoice in invoice_proxy:
            key = (
                #invoice.partner_id.name,
                invoice.account_id.name,
                invoice.number, 
                )
            if key not in invoice_db:
                invoice_db[key] = []
            invoice_db[key].append(invoice)

        
        return {
            'type': 'ir.actions.act_window_close'
            }

    _columns = {
        'partner_id': fields.many2one(
            'res.partner', 'Partner', required=True),
        'account_id': fields.many2one(
            'account.analytic.account', 'Account'),
        #'user_id': fields.many2one(
        #    'res.users', 'User'),
        'from_date': fields.date('From date >= ', required=True),
        'to_date': fields.date('To date <', required=True),
        'float_time': fields.boolean('Formatted hour', 
            help='If checked print hour in HH:MM format'),
        }
        
    _defaults = {
        'float_time': lambda *x: True,
        #'user_id': lambda s, cr, uid, ctx: uid,
        'from_date': lambda *x: datetime.now().strftime('%Y-%m-01'),
        'to_date': lambda *x: (
            datetime.now() + relativedelta(months=1)).strftime('%Y-%m-01'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:



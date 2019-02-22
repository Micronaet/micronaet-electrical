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

class AccountAnalyticAccount(orm.Model):
    """ Model name: AccountAnalyticAccount
    """
    
    _inherit = 'account.analytic.account'
    
    def _get_statinfo_intervent(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate intervent
        '''
        res = {}
        intervent_pool = self.pool.get('hr.analytic.timesheet')
        
        for account in self.browse(cr, uid, ids, context=context):
            res[account.id] = len(
                intervent_pool.search(cr, uid, [
                    ('account_id', '=', account.id),
                    ], context=context))
        return res
        
    def _get_statinfo_move(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate  move
        '''
        res = {}
        move_pool = self.pool.get('stock.move')
        
        for account in self.browse(cr, uid, ids, context=context):
            res[account.id] = len(
                move_pool.search(cr, uid, [
                    ('picking_id.account_id', '=', account.id),
                    ], context=context))
        return res

    def _get_statinfo_picking(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        picking_pool = self.pool.get('stock.picking')
        
        for account in self.browse(cr, uid, ids, context=context):
            res[account.id] = len(
                picking_pool.search(cr, uid, [
                    ('account_id', '=', account.id),
                    ], context=context))
        return res
        
    _columns = {
        'statinfo_intervent': fields.function(
            _get_statinfo_intervent, method=True, 
            type='integer', string='# of intervent', store=False), 
        'statinfo_move': fields.function(
            _get_statinfo_move, method=True, 
            type='integer', string='# of move', store=False), 
        'statinfo_picking': fields.function(
            _get_statinfo_picking, method=True, 
            type='integer', string='# of picking', store=False), 
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

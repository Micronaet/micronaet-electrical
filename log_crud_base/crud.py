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

class LogCrud(orm.Model):
    """ Model name: LogCrud
    """
    
    _name = 'log.crud'
    _description = 'Log CRUD operation'
    _rec_name = 'name'
    _order = 'datetime'
    
    def unlink(self, cr, uid, ids, context=None):
        """ Delete all record(s) from table heaving record id in ids
            return True on success, False otherwise 
            @param cr: cursor to database
            @param uid: id of current user
            @param ids: list of record ids to be removed from table
            @param context: context arguments, like lang, time zone
            
            @return: True on success, False otherwise
        """
        return True
    
    def get_group_partner_ids(self, cr, uid, ids, context=None):
        ''' Return partner for user manage group
        '''
        group_pool = self.pool.get('res.groups')
        data_pool = self.pool.get('ir.model.data')
        group_id = data_pool.get_object_reference(
            cr, uid, 'log_crud_base', 'group_log_crud')[1]
        group = group_pool.browse(cr, uid, group_id, context=context)
        #partner_ids = [user_proxy.company_id.partner_id.id, ]
        import pdb; pdb.set_trace()
        return [user.partner_id.id for user in group.users]

    _columns = {
        'datetime': fields.date('Time stamp', required=True),
        'name': fields.char('Subject', size=80, required=True),
        'user_id': fields.many2one('res.users', 'User', required=True),
        'model_id': fields.many2one('ir.model', 'Objecty'),
        'model_name': fields.char('Model', size=80),
        'mode': fields.selection([
            ('create', 'Create'),
            ('unlink', 'Unlink'),
            ('write', 'Write'),
            ], 'Mode'),
        'note': fields.text('Note'), 
        }
    
    _defaults = {
        'datetime': lambda *x: datetime.now().strftime(
            DEFAULT_SERVER_DATETIME_FORMAT),        
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

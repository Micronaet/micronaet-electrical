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

class IrSequence(orm.Model):
    """ Model name: IrSequence
    """
    
    _inherit = 'ir.sequence'

    def write(self, cr, uid, ids, vals, context=None):
        """ Update redord(s) comes in {ids}, with new value comes as {vals}
            return True on success, False otherwise
            @param cr: cursor to database
            @param uid: id of current user
            @param ids: list of record ids to be update
            @param vals: dict of new values to be set
            @param context: context arguments, like lang, time zone
            
            @return: True on success, False otherwise
        """
    
        # Pool:
        user_pool = self.pool.get('res.users')
        thread_pool = self.pool.get('mail.thread')
        log_pool = self.pool.get('log.crud')

        current_proxy = self.browse(cr, uid, ids, context=context)
        user_proxy = user_pool.browse(cr, uid, uid, context=context)

        now = datetime.now()
        
        # ---------------------------------------------------------------------        
        # Mail message:
        # ---------------------------------------------------------------------        
        partner_ids = log_pool.get_group_partner_ids(
            cr, uid, ids, context=context)

        body = 'Cambio contatore: %s Utente: %s' % (
            current_proxy.name,
            user_proxy.name,
            )
        message = 'Cambio contatore %s: Utente: %s - %s\nDati: %s' % (
            current_proxy.name,
            user_proxy.name,
            now,
            vals,
            )
        thread_pool.message_post(cr, uid, False, 
            type='email', 
            body=body, 
            subject=message,
            partner_ids=[(6, 0, partner_ids)],
            context=context,
            )

        # ---------------------------------------------------------------------        
        # Log crud:
        # ---------------------------------------------------------------------        
        log_pool.create(cr, uid, {
            'name': body,
            'user_id': uid,
            #'model_id': 
            'model_name': 'ir.sequence',
            'mode': 'write',
            'note': message, 
            }, context=context)

        return super(IrSequence, self).write(
            cr, uid, ids, vals, context=context)
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

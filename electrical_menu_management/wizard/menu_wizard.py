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


class MenuItemCreateWizard(orm.TransientModel):
    ''' Wizard for
    '''
    _name = 'menu.item.create.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_create(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        
        
        menu_pool = self.pool.get('ir.ui.menu')
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]

        data = {
            'is_custom': True,
            # TODO parent left and parent_right
            'name': wiz_browse.name,
            'sequence': wiz_browse.sequence,
            'parent_id': wiz_browse.parent_id.id,
            # TODO group
            }
        
        source = wiz_browse.source_id
        if source:
            action = source.action
            if action:
                data['action'] = '%s,%s' % (action._model, action.id)
            else:
                raise osv.except_osv(
                    _('Error'), 
                    _('Menu not have an action associated!'),
                    )
        return menu_pool.create(cr, uid, data, context=context)        

    _columns = {
        'sequence': fields.integer('Seq.', required=True),
        'name': fields.char('Name', size=64, required=True),
        'parent_id': fields.many2one(
            'ir.ui.menu', 'Parent', help='No parent so master top menu'),
        'group_ids': fields.many2many(
            'res.groups', 'menu_groups_wiz_rel', 
            'wizard_id', 'group_id', 'Group'),
        'source_id': fields.many2one(
            'ir.ui.menu', 'Source', help='Select menu that must be copied'),
        }
        
    _defaults = {
        'sequence': lambda *x: 10,
        }    

class IrUiMenu(orm.Model):
    """ Model name: IrUiMenu
    """
    
    _inherit = 'ir.ui.menu'
    
    _columns = {
        'is_custom': fields.boolean('Is custom'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


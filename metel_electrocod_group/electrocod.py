# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
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


class ProductCategory(orm.Model):
    """ Model name: Product cagegory:   
        Create structure: ELECTROCOD
    """
    _inherit = 'product.category'

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    def get_electrocod_category(self, cr, uid, code='ELECTROCOD', 
            name=False, parent_id=False, context=None):
        ''' Create and return missed product category:
        '''
        group_ids = self.search(cr, uid, [
            #('parent_id', '=', parent_id), # for search without parent_id
            ('electrocod_code', '=', code),
            ], context=context)
        if group_ids:    
            # Update:
            self.write(cr, uid, group_ids, {
                'metel_mode': 'electrocod',
                }, context=context)
            return group_ids[0]        
        else:
            return self.create(cr, uid, {
                'parent_id': parent_id,
                'electrocod_code': code,
                'name': name or code or '?',
                'metel_mode': 'electrocod',
                }, context=context)
        
    def scheduled_electrocod_import_data(self, cr, uid, filename=False, 
            root_name='ELECTROCOD', ec_check=37, context=None):
        ''' Import all electrocod group structure 
            filename: fullname of electrocod csv file            
            root_name: Root group name and code (used as KEY!)
            ec_check: char in file where start code of electrocod
        '''
        _logger.info('Electrocod import!')
        not_found = 'NOTFOUND'

        # ---------------------------------------------------------------------
        # Get or create root node:
        # ---------------------------------------------------------------------
        # Root category: ELECTROCOD
        root_id = self.get_electrocod_category(
            cr, uid, code=root_name, context=context)

        # Missed category: NOTFOUND (create but not used here)    
        missed_id = self.get_electrocod_category(
            cr, uid, code='NOTFOUND', parent_id=root_id, context=context)

        # ---------------------------------------------------------------------
        # Read all file and save in database:
        # ---------------------------------------------------------------------
        filename = os.path.expanduser(filename)        
        f_code = open(filename, 'r')
        i = 0
        levels = {} # saved with level        
        line_text = f_code.read()
        lines = line_text.split('\r')        
        
        code = False # Used also for append name splitted on next line
        code_level = False
        no_name_start = ('0', '1')
        for line in lines:
            i += 1
            line = line.strip()
            if line[ec_check + 2: ec_check + 3] != '.' and \
                    line[ec_check + 3: ec_check + 4] != '-': # Dot position
                    
                # Append part in new line for name:    
                if line[0:1] not in no_name_start: # Part of name in new line                
                    part = ' ' + ' '.join(filter(
                        lambda x:x and x[:1] not in no_name_start, 
                        '{}'.format(line.split(' '))))
                        # line.split(' ')))
                    levels[level][code] += part
                    
                continue # no data line
            data = line[ec_check:].split(' - ')
            if len(data) != 2:
                _logger.error('No standard Electrocode line: %s' % line)
                continue
            
            # -----------------------------------------------------------------
            # Manage level:    
            # -----------------------------------------------------------------
            code = data[0].strip()
            name = u'{}'.format(data[1].strip())
            #name = data[1].strip()

            code_level = code.split('.')
            level = len(code_level)
            
            # -----------------------------------------------------------------
            # Save record for creation (next loop)
            # -----------------------------------------------------------------
            if level not in levels:
                levels[level] = {}                
            levels[level][code] = name         
        f_code.close()
        
        nodes = {
            # Master node has no code for search
            root_name: root_id, # Not used only for collect correct key
            '': root_id, # Used with join no level
            }
        for level in sorted(levels):
            for code, name in levels[level].iteritems():
                code_part = code.split('.')
                code_node = code.replace('.', '')
                code_parent = ''.join(code_part[:-1]) # Code without .
                parent_id = nodes.get(code_parent, False)
                if not parent_id:
                    _logger.error('Parent not found: %s' % code_parent)
                    continue

                group_ids = self.search(cr, uid, [
                    ('parent_id', '=', parent_id),
                    ('electrocod_code', '=', code),
                    ], context=context)
                data = {
                    'parent_id': parent_id,
                    'electrocod_code': code,
                    'name': name,
                    'metel_mode': 'electrocod',
                    }
                if group_ids:
                    self.write(cr, uid, group_ids[0], data, context=context)
                    nodes[code_node] = group_ids[0]      
                    _logger.info('Node update: [%s] %s' % (code, name))    
                else:
                    nodes[code_node] = self.create(cr, uid, data, 
                        context=context)
                    _logger.info('Node create: [%s] %s' % (code, name))    
        _logger.info('Electrocod import end!')
        return nodes

    _columns = {
        'electrocod_code': fields.char('Electrocod code', size=18, 
            help='Electrocod code'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

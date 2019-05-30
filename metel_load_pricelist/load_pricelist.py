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
import shutil
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


# Module parameters: Mode list for file
file_mode = [
    'LSP', # 1. Public pricelist
    'FST', # 2. Statistic family
    'FSC', # 3. Discount family
    #'LSG', #Reseller pricelist
    #'RIC', #Recode
    #'BAR', #Barcode
    ]

class MetelProducerFile(orm.Model):
    """ Model name: MetelProducerFile
    """
    
    _name = 'metel.producer.file'
    _description = 'Metel file'
    _rec_name = 'name'
    _order = 'name'

    # -------------------------------------------------------------------------    
    # Button event:
    # -------------------------------------------------------------------------    
    def dummy(self, cr, uid, ids, context=None):
        """ dummy event
        """       
        return True    

    def update_mode_this(self, cr, uid, ids, context=None):
        ''' Launch update mode 
        '''
        param_pool = self.pool.get('metel.parameter')
        if context is None:
            context = {}
        context['update_mode'] = ids # only this
        return param_pool.schedule_import_pricelist_action(
            cr, uid, verbose=True, context=context)

    def update_mode_all(self, cr, uid, ids, context=None):
        ''' Launch update mode 
        '''        
        param_pool = self.pool.get('metel.parameter')
        if context is None:
            context = {}
        context['update_mode'] = self.search(cr, uid, [
            ('state', '=', 'updated'),
            ('force_update_mode', '!=', False),
            ], context=context)
        return param_pool.schedule_import_pricelist_action(
            cr, uid, verbose=True, context=context)

    # -------------------------------------------------------------------------    
    # Workflow event:
    # -------------------------------------------------------------------------    
    def wf_force_reload(self, cr, uid, ids, context=None):
        ''' WF: Force button 
        '''
        #param_pool = self.pool.get('metel.parameter')
        #timestamp = param_pool.get_modify_date(current.fullname)                
        return self.write(cr, uid, ids, {
            'state': 'draft',
            #'datetime': timestamp,
            'timestamp': False, # Reset timestamp
            }, context=context)
            
    def wf_mark_updated(self, cr, uid, ids, context=None):
        ''' WF: Force updated 
        '''
        current = self.browse(cr, uid, ids, context=context)
        param_pool = self.pool.get('metel.parameter')
        timestamp = param_pool.get_modify_date(current.fullname)                
        return self.write(cr, uid, ids, {
            'state': 'updated',
            'timestamp': timestamp,
            'datetime': timestamp,
            }, context=context)
            
    def wf_set_obsolete(self, cr, uid, ids, context=None):
        ''' WF: Obsolete button 
        '''
        return self.write(cr, uid, ids, {
            'state': 'obsolete',
            }, context=context)

    _columns = {
        'name': fields.char('Filename', size=80, required=True),
        'filename': fields.char('Filename', size=80, required=True, 
            help='Real file name in case sensitive!'),
        'fullname': fields.char('Fullname', size=200, required=True, 
            help='Real fullname in case sensitive!'),
        'timestamp': fields.datetime('Updated confirm'),
        'init': fields.datetime('Init timestamp'),
        'datetime': fields.datetime('Current timestamp'),
        'log': fields.text('Log', help='Log last import event'),
        'force_update_mode': fields.selection([
            ('uom', 'UOM'), # New files was found
            ('price', 'Price'), # Update after import
            ], 'Fast update'),
        'state': fields.selection([
            ('draft', 'New'), # New files was found
            ('updated', 'Updated'), # Update after import

            ('forced', 'Force reload'), # Force reload when scheduled
            ('wrong', 'Wrong format'), # Not correct format or name
            ('obsolete', 'Obsolete or deleted'), # No more used
            ], 'State'),
        }

    _defaults = {
        'state': lambda *x: 'draft',
        }    

class MetelBase(orm.Model):
    """ Model name: MetelBase
    """
    
    _inherit = 'metel.parameter'

    # -------------------------------------------------------------------------
    # Utility:    
    # -------------------------------------------------------------------------
    def get_modify_date(self, fullname):
        ''' Return modify date for file
        '''
        st_mtime = os.stat(fullname).st_mtime
        return datetime.fromtimestamp(st_mtime).strftime(
            DEFAULT_SERVER_DATETIME_FORMAT)
    
    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    def update_file_record_from_folder(self, cr, uid, ids, context=None):
        ''' Force init setup, load all file present and mark as imported
        '''
        file_pool = self.pool.get('metel.producer.file')

        # Read parameter
        param_ids = self.search(cr, uid, [], context=context)
        param_proxy = self.browse(cr, uid, param_ids, context=context)[0]
        data_folder = os.path.expanduser(param_proxy.root_data_folder)
        
        # ---------------------------------------------------------------------
        # Load current ODOO:
        # ---------------------------------------------------------------------
        odoo_files = {}
        file_ids = file_pool.search(cr, uid, [], context=None)
        for record in file_pool.browse(
                cr, uid, file_ids, context=context):
            odoo_files[record.fullname] = record    
            
        # ---------------------------------------------------------------------
        # Read input master folder:
        # ---------------------------------------------------------------------
        # TODO mark no mode present
        for root, dirs, files in os.walk(data_folder):
            for filename in files:
                fullname = os.path.join(root, filename)          
                file_mode_code = filename[3:6]

                if filename.endswith('~') or filename.startswith('.'):
                    _logger.warning('Jump TEMP/HIDDEN file: %s' % fullname)
                    continue
                    
                if file_mode_code not in file_mode: # Not imported
                    _logger.warning('Jump METEL file: %s (not in %s)' % (
                        fullname, file_mode,
                        ))
                    continue    

                timestamp = self.get_modify_date(fullname)                
                if fullname in odoo_files:
                    # Update and check
                    record = odoo_files[fullname]
                    if record.timestamp != timestamp:
                        # reload delete record timestamp!
                        file_pool.wf_force_reload(
                            cr, uid, [record.id], context=context)
                    del(odoo_files[fullname]) # remove for check 
                else:
                    file_pool.create(cr, uid, {
                        'name': filename.upper(),
                        'filename': filename,
                        'fullname': fullname,
                        'init': timestamp,
                        'datetime': timestamp,
                        #'timestamp': timestamp_value, # will be reloaded!
                        #'log': fields.text('Log', help='Log last import event'),
                        #'state'
                        }, context=context)

            break # only master folder
            
        # Update no more present files:
        if odoo_files:
            file_pool.wf_set_obsolete(cr, uid, [
                record.id for record in odoo_files.values()], context=context)
                
        return True

    # Scheduled event:
    def schedule_import_pricelist_action(self, cr, uid, verbose=True, 
            context=None):
        ''' Schedule import of pricelist METEL
        '''
        if context is None:
            context = {}
        update_mode = context.get('update_mode', False)    

        # Pool used:
        product_pool = self.pool.get('product.product') 
        category_pool = self.pool.get('product.category')
        file_pool = self.pool.get('metel.producer.file')

        # Update record from folder:
        self.update_file_record_from_folder(cr, uid, False, context=context)

        # --------------------------------------------------------------------- 
        # Read parameter
        # --------------------------------------------------------------------- 
        # Database parameters:
        param_ids = self.search(cr, uid, [], context=context)
        param_proxy = self.browse(cr, uid, param_ids, context=context)[0]

        # Electrocod data:
        electrocod_code = param_proxy.electrocod_code
        electrocod_start_char = param_proxy.electrocod_start_char
        electrocod_file = param_proxy.electrocod_file
        
        if electrocod_code and electrocod_start_char and electrocod_file:
            electrocod_file = os.path.expanduser(electrocod_file)
            electrocod_db = category_pool.scheduled_electrocod_import_data(
                cr, uid, 
                filename=electrocod_file, 
                root_name=electrocod_code, 
                ec_check=electrocod_start_char, 
                context=context)
        else:
            electrocod_db = {}
            _logger.error('''
                Setup Electrocod parameter for get correct management!
                (no group Electrocod structure created, no association with 
                product created)''')
        
        # If not fount Code category (new code) use a missed one!        
        missed_id = category_pool.get_electrocod_category(
            cr, uid, code='NOTFOUND', context=context)        
                
        # Linked object DB:
        currency_db = self.load_parse_text_currency(cr, uid, context=context)
        uom_db = self.load_parse_text_uom(cr, uid, context=context)
        
        # --------------------------------------------------------------------- 
        # Import procecedure:
        # --------------------------------------------------------------------- 
        # 1. Loop pricelist folder:
        created_group = []        
        if update_mode:
            file_ids = update_mode
        else:    
            file_ids = file_pool.search(cr, uid, [
                ('state', '=', 'draft'),
                ('timestamp', '=', False),
                ], context=context)

        for record in file_pool.browse(cr, uid, file_ids, context=context):
            logger = [] # List of error (reset every file)
            filename = record.filename
            fullname = record.fullname
            force_update_mode = record.force_update_mode
                            
            # Parse filename:
            file_producer_code = filename[:3]
            file_mode_code = filename[3:6]

            # TODO version?
            currency = (filename.split('.')[0])[6:]
            metel_producer_id = category_pool.get_create_producer_group(
                cr, uid, file_producer_code, file_producer_code,
                context=context)

            if verbose:
                _logger.info('Read METEL file: %s' % fullname)

            i = upd = new = 0
            uom_missed = []
            f_metel = open(fullname, 'r')
            line_len = 0
            for line in f_metel:
                i += 1
                # ---------------------------------------------------------
                # Header:
                # ---------------------------------------------------------
                if i == 1:
                    if verbose:
                        _logger.info('%s. Read header METEL' % i)
                    # TODO
                    continue
                
                # Check len line:    
                if not line_len:
                    line_len = len(line)
                if line_len != len(line):
                    if verbose:
                        _logger.error(
                            '%s. Different lenght: %s' % (i, line_len))
                    continue
                
                # ---------------------------------------------------------
                #                    MODE: LSP (Pricelist full)
                # ---------------------------------------------------------
                if file_mode_code == 'LSP':                    
                    # Data row:
                    brand_code = self.parse_text(
                        line[0:3], logger=logger) # TODO create also category
                    default_code = self.parse_text(
                        line[3:19], logger=logger)
                    
                    # ---------------------------------------------------------    
                    # Standard mode:
                    # ---------------------------------------------------------    
                    if not update_mode:
                        ean13 = self.parse_text(
                            line[19:32], logger=logger)
                        name = self.parse_text(
                            line[32:75], logger=logger)
                        metel_q_x_pack = self.parse_text(
                            line[75:80], logger=logger)
                        metel_order_lot = self.parse_text_number(
                            line[80:85], logger=logger)
                        metel_order_min = self.parse_text_number(
                            line[85:90], logger=logger)
                        metel_order_max = self.parse_text_number(
                            line[90:96], logger=logger)
                        metel_leadtime = self.parse_text_number(
                            line[96:97], logger=logger)

                        metel_kit = self.parse_text_boolean(
                            line[131:132], logger=logger)     
                        metel_state = self.parse_text(
                            line[132:133], logger=logger)
                        metel_last_variation = self.parse_text_date(
                            line[133:141], logger=logger)
                        metel_discount = self.parse_text(
                            line[141:159], logger=logger)
                        metel_statistic = self.parse_text(
                            line[159:177], logger=logger)
                        metel_electrocod = self.parse_text(
                            line[177:197], logger=logger)
                    
                        # Alternate value for EAN code:
                        metel_alternate_barcode = self.parse_text(
                            line[197:232], logger=logger)
                        metel_alternate_barcode_type = self.parse_text(
                            line[232:233], logger=logger)
                    
                    # ---------------------------------------------------------
                    # Update mode:
                    # ---------------------------------------------------------
                    # UOM Mode:
                    if not update_mode or force_update_mode == 'uom':
                        uom = self.parse_text(
                            line[128:131], logger=logger)

                        # UOM manage:
                        uom_id = uom_db.get(uom, False)
                        if not uom_id and uom not in uom_missed: # Log missed
                            uom_missed.append(uom)

                    # Reseller price mode:    
                    if not update_mode or force_update_mode == 'price':
                        lst_price = self.parse_text_number(
                            line[97:108], 2, logger=logger) 
                        # public price:    
                        metel_list_price = self.parse_text_number(
                            line[108:119], 2, logger=logger) 
                        metel_multi_price = self.parse_text_number(
                            line[119:125], logger=logger)
                        currency = self.parse_text(
                            line[125:128], logger=logger)
                        
                        # Manage multi price value:
                        if metel_multi_price > 1:
                            metel_list_price /= metel_multi_price
                            lst_price /= metel_multi_price
                        # TODO use currency    

                    # ---------------------------------------------------------
                    
                    # Code = PRODUCER || CODE
                    default_code = '%s%s' % (brand_code, default_code)

                    if not update_mode:
                        # Category with Electrocod:
                        if metel_electrocod:
                            categ_id = electrocod_db.get(
                                metel_electrocod, missed_id)                    
                        else:    
                            categ_id = missed_id 
                        
                        # Create brand group:
                        if (file_producer_code, brand_code) in created_group: 
                            metel_brand_id = created_group[
                                (file_producer_code, brand_code)]
                        else:
                            metel_brand_id = \
                                category_pool.get_create_brand_group(
                                    cr, uid, file_producer_code, brand_code, 
                                    brand_code, 
                                    # name = code (modify in anagraphic)
                                    context=context)

                    # -----------------------------------------------------
                    # Create record data:
                    # -----------------------------------------------------
                    # Master data (common part):
                    data = {
                        'is_metel': True,
                        'metel_auto': True,
                        'default_code': default_code,
                        }

                    # ---------------------------------------------------------
                    # Update mode:
                    # ---------------------------------------------------------
                    # UOM:
                    if not update_mode or force_update_mode == 'uom':
                        data.update({    
                            # Update mode (all cases):
                            'metel_uom': uom,
                            })
                    # Price:        
                    if not update_mode or force_update_mode == 'price':
                        data.update({    
                            'metel_q_x_pack': metel_q_x_pack,
                            'lst_price': lst_price,
                            'metel_multi_price': metel_multi_price,    
                            'metel_list_price': metel_list_price,
                            }
                        
                    # ---------------------------------------------------------
                    # Standard mode:
                    # ---------------------------------------------------------
                    if not update_mode:
                        data.update({    
                            'type': 'product', 
                            'metel_producer_id': metel_producer_id,
                            'metel_brand_id': metel_brand_id,                                                
                            'metel_producer_code': file_producer_code,
                            'metel_brand_code': brand_code,

                            'ean13': ean13,
                            'name': name,
                            'categ_id': categ_id,
                            'metel_order_lot': metel_order_lot,
                            'metel_order_min': metel_order_min,
                            'metel_order_max': metel_order_max,
                            'metel_leadtime': metel_leadtime,
                            'metel_kit': metel_kit,
                            'metel_state': metel_state,
                            'metel_last_variation': metel_last_variation,
                            'metel_discount': metel_discount,
                            'metel_statistic': metel_statistic,                        
                            'metel_electrocod': metel_electrocod,
                            'metel_alternate_barcode': 
                                metel_alternate_barcode,
                            'metel_alternate_barcode_type': 
                                metel_alternate_barcode_type,
                        })

                    # TODO Extra data: discount management for price?    
                    # -----------------------------------------------------
                    # Update database:
                    # -----------------------------------------------------
                    product_ids = product_pool.search(cr, uid, [
                         ('default_code','=', default_code),
                         # Not necessary, code has brand code in it
                         #('metel_brand_code', '=', brand_code),
                         ], context=context)

                    if product_ids: 
                        #`TODO update forced UM:
                        if update_mode:
                            self.update_force_uom_id(
                                cr, uid, ids, product_ids, context=context)
                        try:
                            product_pool.write(
                                cr, uid, product_ids, data, 
                                context=context)
                            # XXX UOM not updated:
                        except:
                            logger.append(
                                _('Error updating: %s' % default_code))
                            continue
                        if verbose:
                            upd += 1
                            _logger.info('%s. Update %s' % (
                                i, default_code))
                    else:        
                        data['uom_id'] = uom_id
                        try:
                            product_pool.create(
                                cr, uid, data, context=context)
                        except:
                            logger.append(
                                _('Error updating: %s' % default_code))
                            continue
                        if verbose:
                            new += 1
                            _logger.info('%s. Create %s' % (
                                i, default_code))

                # ---------------------------------------------------------
                #                    MODE: FST (Statistic family)
                # ---------------------------------------------------------
                elif file_mode_code in ('FST', 'FSC'):
                    if file_mode_code == 'FST':
                        field = 'metel_statistic'
                        field_id = 'metel_statistic_id'
                        metel_mode = 'statistic'
                    else:
                        field = 'metel_discount'
                        field_id = 'metel_discount_id'
                        metel_mode = 'discount'
                            
                    # Data row:
                    producer_code = self.parse_text(
                        line[0:3], logger=logger)
                    brand_code = self.parse_text(
                        line[3:6], logger=logger)
                    metel_code = self.parse_text(
                        line[6:24], logger=logger)
                    name = self.parse_text(
                        line[24:], logger=logger)
                    
                    # -----------------------------------------------------
                    # Create producer > brand groups:
                    # -----------------------------------------------------
                    if (file_producer_code, brand_code) in created_group: 
                        metel_brand_id = created_group[
                            (file_producer_code, brand_code)]
                    else:
                        metel_brand_id = \
                            category_pool.get_create_brand_group(
                                cr, uid, file_producer_code, brand_code, 
                                brand_code, context=context)
                    
                    # -----------------------------------------------------
                    # Crete or get statistic/discount category:            
                    # -----------------------------------------------------
                    category_ids = category_pool.search(cr, uid, [
                        ('parent_id', '=', metel_brand_id),
                        (field, '=', metel_code),
                        ], context=context)
                    data = {
                        'parent_id': metel_brand_id,
                        field: metel_code,
                        'name': name,
                        'metel_mode': metel_mode,
                        }    
                    if category_ids:
                        metel_code_id = category_ids[0]    
                        category_pool.write(
                            cr, uid, category_ids, data, context=context)
                    else:
                        metel_code_id = category_pool.create(
                            cr, uid, data, context=context)

                    # -----------------------------------------------------
                    # Update product of this category with serie:
                    # -----------------------------------------------------
                    product_ids = product_pool.search(cr, uid, [
                        ('metel_producer_code', '=', producer_code),
                        ('metel_brand_code', '=', brand_code),                            
                        (field, '=', metel_code),
                        (field_id, '!=', metel_code_id),
                        ], context=context)
                        
                    data = {field_id: metel_code_id, }
                    
                    # Update series fron statistic (if FST)
                    if file_mode_code == 'FST':
                        metel_statistic_proxy = category_pool.browse(
                            cr, uid, metel_code_id, context=context)
                        if metel_statistic_proxy.metel_serie_id:
                            data['metel_serie_id'] = \
                                metel_statistic_proxy.metel_serie_id.id

                    product_pool.write(cr, uid, product_ids, data, 
                        context=context)    

                    if verbose:
                        _logger.info('%s. Update # %s with %s' % (
                            i, len(product_ids), metel_code))

                # -------------------------------------------------------------
                #                    MODE: UNMANAGED!
                # -------------------------------------------------------------
                else:
                    if verbose:
                        _logger.info(
                            'Unmanaged file code: %s' % file_mode_code)
                                            
            # -----------------------------------------------------------------
            #                      COMMON PART:
            # -----------------------------------------------------------------
            f_metel.close()
            
            # -----------------------------------------------------------------
            # Log operation
            # -----------------------------------------------------------------
            # Add extra log for UOM:
            if uom_missed:
                logger.append(_('Missed UOM code: %s') % uom_missed)

            # -----------------------------------------------------------------
            # Update file record for operazion:
            # -----------------------------------------------------------------
            # Write log status if present:
            if logger:
                file_pool.write(cr, uid, [record.id], {
                    'log': '\n'.join(tuple(logger))
                    }, context=context)
           
            # Update mode clean record:         
            if update_mode:
                file_pool.write(cr, uid, [record.id], {
                    'force_update_mode': False
                    }, context=context)
                
            # Mark as updated:
            file_pool.wf_mark_updated(cr, uid, [record.id], context=context)
            
            # -------------------------------------------------------------
            # System log operation:
            # -------------------------------------------------------------
            if verbose:
                _logger.info(
                    'File: %s record: %s [UPD %s NEW %s]' % (
                        filename, i, upd, new,
                        ))
                _logger.info('UOM missed [%s]' % (uom_missed, ))                    

        return True
        
    _columns = {
        'root_data_folder': fields.char('Root folder', size=120, 
            help='~/.filestore/metel'),

        'electrocod_code': fields.char('Code', size=20,
            help='Name and code for first root group'),
        'electrocod_start_char': fields.integer('Start data char'),
        'electrocod_file': fields.char('Electrodoc file', size=120,
            help='~/.filestore/metel/electrocod.txt'),                     
        }
        
    _defaults = {
        'electrocod_code': lambda *x: 'ELECTROCOD',
        'electrocod_start_char': lambda *x: 37,
        }

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'

    # -------------------------------------------------------------------------
    # Button event:    
    # -------------------------------------------------------------------------
    def update_metel_discount_all_product(self, cr, uid, ids, context=None):
        ''' Create discount category from discount code 
            Update all product with that code
        '''
        category_pool = self.pool.get('product.category')
        product = self.browse(cr, uid, ids, context=context)[0]

        # Parameter product:
        producer_code = product.metel_producer_code
        brand_code = product.metel_brand_code
        metel_discount = product.metel_discount

        # ---------------------------------------------------------------------
        # Check availability:        
        # ---------------------------------------------------------------------
        # Producer ID
        if not product.metel_producer_id:
            raise osv.except_osv(
                _('Error'), 
                _('Product without producer group'),
                )

        # Brand code:
        if not product.metel_brand_code:
            raise osv.except_osv(
                _('Error'), 
                _('Product without brand code'),
                )

        # Discount code:
        if not metel_discount:
            raise osv.except_osv(
                _('Error'), 
                _('Product without metel discount code'),
                )

        # metel_discount_id is check on visibiliy (view)

        # ---------------------------------------------------------------------        
        # Create discount group:
        # ---------------------------------------------------------------------        
        if not product.metel_brand_id: # Metel brand not yet created
            metel_brand_id = category_pool.get_create_brand_group(
                producer_code, brand_code, brand_code)
        else:
            metel_brand_id = product.metel_brand_id.id
            
        # Search discount category:    
        category_ids = category_pool.search(cr, uid, [
            ('parent_id', '=', metel_brand_id),
            ('metel_discount', '=', metel_discount), # code
            ('metel_mode', '=', 'discount'),
            ], context=context)

        if category_ids:
            metel_discount_id = category_ids[0]
        else:
            metel_discount_id = category_pool.create(cr, uid, {
                'parent_id': metel_brand_id,
                'metel_discount': metel_discount,
                'name': metel_discount,
                'metel_mode': 'discount',
                }, context=context)
        # ---------------------------------------------------------------------        
        # Update all product
        # ---------------------------------------------------------------------        
        product_ids = self.search(cr, uid, [
            ('metel_brand_code', '=', brand_code),
            ('metel_discount', '=', metel_discount),
            ('metel_discount_id', '=', False),
            ], context=context)

        self.write(cr, uid, product_ids, {
            'metel_discount_id': metel_discount_id,
            }, context=context)
        _logger.warning('Updating %s product with discount: %s' % (
            len(product_ids),
            metel_discount,
            ))
        return True    
        
    # -------------------------------------------------------------------------
    # Button event:    
    # -------------------------------------------------------------------------
    def update_metel_statistic_all_product(self, cr, uid, ids, context=None):
        ''' Create statistic category from discount code 
            Update all product with that code
        '''
        category_pool = self.pool.get('product.category')
        product = self.browse(cr, uid, ids, context=context)[0]

        # Parameter product:
        producer_code = product.metel_producer_code
        brand_code = product.metel_brand_code
        metel_statistic = product.metel_statistic

        # ---------------------------------------------------------------------
        # Check availability:        
        # ---------------------------------------------------------------------
        # Producer ID
        if not product.metel_producer_id:
            raise osv.except_osv(
                _('Error'), 
                _('Product without producer group'),
                )

        # Brand code:
        if not product.metel_brand_code:
            raise osv.except_osv(
                _('Error'), 
                _('Product without brand code'),
                )

        # Statistic code:
        if not metel_statistic:
            raise osv.except_osv(
                _('Error'), 
                _('Product without metel statistic code'),
                )

        # ---------------------------------------------------------------------        
        # Create statistic group:
        # ---------------------------------------------------------------------        
        if not product.metel_brand_id: # Metel brand not yet created
            metel_brand_id = category_pool.get_create_brand_group(
                producer_code, brand_code, brand_code)
        else:
            metel_brand_id = product.metel_brand_id.id
            
        # Search statistic category:    
        category_ids = category_pool.search(cr, uid, [
            ('parent_id', '=', metel_brand_id),
            ('metel_statistic', '=', metel_statistic), # code
            ('metel_mode', '=', 'statistic'),
            ], context=context)

        if category_ids:
            metel_statistic_id = category_ids[0]
        else:
            metel_statistic_id = category_pool.create(cr, uid, {
                'parent_id': metel_brand_id,
                'metel_statistic': metel_statistic,
                'name': metel_statistic,
                'metel_mode': 'statistic',
                }, context=context)
        # ---------------------------------------------------------------------        
        # Update all product
        # ---------------------------------------------------------------------        
        product_ids = self.search(cr, uid, [
            ('metel_brand_code', '=', brand_code),
            ('metel_statistic', '=', metel_statistic),
            ('metel_statistic_id', '=', False),
            ], context=context)

        self.write(cr, uid, product_ids, {
            'metel_statistic_id': metel_statistic_id,
            }, context=context)
        _logger.warning('Updating %s product with statistic: %s' % (
            len(product_ids),
            metel_statistic,
            ))
        return True    
            
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

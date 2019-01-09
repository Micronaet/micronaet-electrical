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

class MetelMetel(orm.Model):
    """ Model name: MetelMetel
    """
    
    _name = 'metel.parameter'
    _description = 'Metel parameter'
    _order = 'company_id'
    
    # -------------------------------------------------------------------------
    #                      Utility for manage METEL file:
    # -------------------------------------------------------------------------
    
    # -------------------------------------------------------------------------
    # Parse function for type:
    # -------------------------------------------------------------------------
    def parse_text(self, text, logger=None):
        ''' Clean text
            logger: logger list for collect error during import     
        '''
        if logger is None:
            logger = []
        try:    
            return text.strip()
        except:
            logger.append(_('Error converting text %s') % text)
            return '?'

    def parse_text_boolean(self, text, logger=None):
        ''' Clean text
            logger: logger list for collect error during import     
        '''
        if logger is None:
            logger = []
        try:    
            return text.strip() == '1'
        except:
            logger.append(_('Error converting text boolean %s') % text)
            return False

    def parse_text_number(self, text, decimal=0, logger=None):
        ''' Parse text value for float number according with METEL template           
            In METEL numbers has NN.DD format 
            ex.: 10.2 = total char 10, last 2 is decimal so:
                 NNNNNNNNDD  >> 0000001234 means 12.34
            decimal = DD number, ex.: 10.2 >> 2 is decimal
                if decimal = 0 return interger
            logger: logger list for collect error during import     
        '''
        if logger is None:
            logger = []
            
        try:
            if decimal:
                return float('%s.%s' % (
                    text[:-decimal],
                    text[-decimal:],
                    ))            
            else: 
                return int(text)        
        except:
            logger.append(_('Error converting float %s (decimal: %s)') % (
                text, decimal))
            return 0.0 # nothing
        
    def parse_text_date(self, text, mode='YYYYMMDD', logger=None):
        ''' Parse text value for date value according with METEL template           
            METEL format YYYYMMDD (Iso without char)
            logger: logger list for collect error during import             
        '''
        if logger is None:
            logger = []

        if not text or not text.strip():
            return False
            
        if mode == 'YYYYMMDD':
            return '%s-%s-%s' % (
                text[:4],
                text[4:6],
                text[6:8],
                )
        #else: # XXX no way always mode is present!
        return False

    # -------------------------------------------------------------------------
    # Load database for parsing:
    # -------------------------------------------------------------------------
    def load_parse_text_currency(self, cr, uid, context=None):
        ''' Parse text value for currency ID according with METEL code
        '''
        res = {}
        currency_pool = self.pool.get('res.currency')
        currency_ids = currency_pool.search(cr, uid, [], context=context)
        for currency in currency_pool.browse(cr, uid, currency_ids,
                context=context):
            res[currency.name] = currency.id
        return res

    def load_parse_text_uom(self, cr, uid, context=None):
        ''' Parse text value for uom ID according with METEL code
            Used:
            PCE Pezzi - BLI Blister - BRD Cartoni - KGM Chilogrammi
            LE Litri - LM Metri lineari - PL Pallet
        '''
        res = {}
        uom_pool = self.pool.get('product.uom')
        uom_ids = uom_pool.search(cr, uid, [], context=context)
        for uom in uom_pool.browse(cr, uid, uom_ids,
                context=context):
            if uom.metel_code:
                res[uom.metel_code] = uom.id
        return res

    #def parse_text_country(self, value):
    #    ''' Parse text value for country ID according with METEL template           
    #    '''
    #    return value
        
    _columns = {
        'company_id': fields.many2one(
            'res.company', 'Company', required=True),            
        }

    _sql_constraints = [('company_id_uniq', 'unique (company_id)', 
        'Parameter for that company already present!')]

class ProductUom(orm.Model):
    """ Model name: ProductUom
    """    
    _inherit = 'product.uom'
    
    _columns = {
        'metel_code': fields.char('Metel code', size=18),
        }

#class ResPartner(orm.Model):
#    """ Model name: Res Partner
#    """    
#    _inherit = 'res.partner'
#    
#    _columns = {
#        'metel_code': fields.char('Metel code', size=18),
#        }

class ProductCategory(orm.Model):
    """ Model name: Product cagegory:   
        Create structure: METEL / Producer / Brand
    """
    _inherit = 'product.category'
    
    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    def get_create_metel_group(self, cr, uid, code, name=False, 
            parent_id=False, metel_mode=False, context=None):
        ''' Get (or create if not present) producer "code" and "name"
        '''
        group_ids = self.search(cr, uid, [
            ('parent_id', '=', parent_id),
            ('metel_code', '=', code),
            ], context=context)
        if group_ids:
            if len(group_ids) > 1:
                _logger.error(_('Code present more than one! [%s]') % code)

            # Update metel mode: XXX (removeable)    
            self.write(cr, uid, group_ids, {
                'metel_mode': metel_mode,
                }, context=context)
            return group_ids[0]
        else:
            data = {
                'parent_id': parent_id,
                'metel_code': code,
                'name': name or code or '',
                'metel_mode': metel_mode,
                }
    
            return self.create(cr, uid, data, context=context)
    
    # Producer group ID:
    def get_create_producer_group(self, cr, uid, 
            producer_code, producer_name=False, context=None):
        ''' Create producer group
        '''
        # Parent root:
        metel_id = self.get_create_metel_group(cr, uid, 
            'METEL', metel_mode='metel', context=context)

        # Producer:
        return self.get_create_metel_group(cr, uid, 
            producer_code, producer_name, metel_id, metel_mode='producer', 
            context=context)

    # Brand group ID:
    def get_create_brand_group(self, cr, uid, 
            producer_code, # must exist!
            brand_code, brand_name,
            context=None):
        ''' Get (or create if not present) producer "code" and "name"
        '''
        # Producer (parent):
        producer_id = self.get_create_producer_group(cr, uid, 
            producer_code, context=context)

        # Brand:
        return self.get_create_metel_group(cr, uid, 
            brand_code, brand_name, producer_id, metel_mode='brand', 
            context=context)
        
    _columns = {
        # ---------------------------------------------------------------------
        # Metel URL generation:
        # ---------------------------------------------------------------------
        # Default:
        'metel_web_prefix': fields.char('Metel web prefix', size=180, 
            help='Metel web prefix, ex: https://www.metel.com/code/'),
        'metel_web_postfix': fields.char('Metel web postfix', size=180, 
            help='Metel web postfix, ex: .php'),

        # Image:
        'metel_web_prefix_image': fields.char('Metel web prefix image', 
            size=180, 
            help='Metel web prefix image, ex: https://www.metel.com/code/'),
        'metel_web_postfix_image': fields.char('Metel web postfix', size=180, 
            help='Metel web postfix, ex: .jpg'),

        # PDF:
        'metel_web_prefix_pdf': fields.char('Metel web prefix PDF', size=180, 
            help='Metel web prefix PDF, ex: https://www.metel.com/code/'),
        'metel_web_postfix_pdf': fields.char('Metel web postfix PDF', size=180, 
            help='Metel web postfix PDF, ex: .pdf'),

        'metel_code': fields.char('Metel code', size=18, 
            help='Metel code: producer of brand'),
        'metel_description': fields.char('Metel description', size=40, 
            help='Metel name: producer or brand'),
        'metel_partner_id': fields.many2one(
            'res.partner', 'Metel Partner', 
            help='If group is a producer element'),
        'metel_serie_id': fields.many2one(
            'product.category', 'Metel serie',
            help='Serie for brand category, used for set up on product'),
        'metel_statistic': fields.char('Statistic code', size=20),    
        'metel_discount': fields.char('Discount code', size=20),    
        # TODO remove is_serie management, use metel_mode
        'is_serie': fields.boolean('Is serie', 
            help='This category is used as a Serie for product and brand'),
        # TODO manage group mode in creation:    
        'metel_mode': fields.selection([            
            ('metel', 'Metel'), # Level 1:            
            ('producer', 'Producer'), # Level 2:            
            ('brand', 'Brand'), # Level 3:
                        
            ('discount', 'Discount category'), # Level 4: 
            ('statistic', 'Statistic category'), # Level 4: 
            
            ('serie', 'Serie'), # Level 5:

            ('electrocod', 'Electrocod'), # Electrocod
            ], 'Metel Mode'),
        }

class ProductProduct(orm.Model):
    """ Model name: Product Product
    """    
    _inherit = 'product.product'

    # -------------------------------------------------------------------------
    # Button action:
    # -------------------------------------------------------------------------
    def open_producer_product_web_link(self, cr, uid, ids, context=None):
        ''' Open URL for producer link
        '''
        product = self.browse(cr, uid, ids, context=context)[0]
        
        return {
            'type': 'ir.actions.act_url',
            'url': product.metel_weblink,
            'target': 'blank',
            }
        
    # -------------------------------------------------------------------------
    # Field function:    
    # -------------------------------------------------------------------------
    def get_url_mode(self, product, mode=''):
        ''' Calculate URL per mode:
            - nothing: default url
            - image: image mode
            - pdf: pdf mode
        '''
        code_remove = 3 # TODO parametrize

        pre_field = 'metel_web_prefix' + mode
        post_field = 'metel_web_postfix' + mode
        
        producer = product.metel_producer_id
        pre = producer.__getattrbute__(pre_field)
        pre = producer.__getattrbute__(post_field)
        if product.default_code and pre:
            return '%s%s%s' % (
                pre or '', 
                product.default_code[code_remove:],
                post or '',
                )
        else:
            return ''        
        
    def _get_producer_web_link(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''    

        res = {}
        for product in self.browse(cr, uid, ids, context=context):
            res[product.id] = {
                'metel_weblink': self.get_url_mode(product),
                'metel_weblink_image': self.get_url_mode(product, 'image'),
                'metel_weblink_pdf': self.get_url_mode(product, 'pdf'),
                }
        return res        

    _columns = {
        #'metel_code': fields.char('Metel code', size=18),
        'is_metel': fields.boolean('Is Metel'),
        'metel_producer_id': fields.many2one(
            'product.category', 'Metel producer'),
        'metel_brand_id': fields.many2one(
            'product.category', 'Metel brand'),
        'metel_serie_id': fields.many2one(
            'product.category', 'Metel serie'),
         
        # Price:    
        'metel_list_price': fields.float('Metel pricelist', 
            digits_compute=dp.get_precision('Product Price')),
        'metel_multi_price': fields.integer('Multi price', 
            help='When price is < 0.01 use multiplicator'),
            
        # Order:    
        'metel_q_x_pack': fields.integer('Q. x pack'),            
        'metel_order_lot': fields.integer('Order lot'),
        'metel_order_min': fields.integer('Order min'),
        'metel_order_max': fields.integer('Order max'),
        'metel_leadtime': fields.integer('Order leadtime'),
        
        # Code:
        'metel_electrocod': fields.char('Electrocod', size=24),    
        'metel_brand_code': fields.char('Brand code', size=10),    
        'metel_producer_code': fields.char('Producer code', size=10),
        
        'metel_kit':fields.boolean('KIT'),
        'metel_last_variation': fields.date('Last variation'),
        'metel_discount': fields.char('Discount', size=20),    
        'metel_discount_id': fields.many2one(
            'product.category', 'Metel discount'),
        'metel_statistic': fields.char('Statistic', size=20),    
        'metel_statistic_id': fields.many2one(
            'product.category', 'Metel statistic'),

        'metel_alternate_barcode': fields.char('Alternate barcode', size=50),    
        'metel_alternate_barcode_type': fields.char('Alternate barcode type', 
            size=6),    
        'metel_state': fields.selection([
            ('1', 'New product'),
            ('2', 'Finished or to be cancel'),
            ('3', 'Managed with stock'),
            ('4', 'New service'),
            ('5', 'Cancelled service'),
            ('6', 'Produced with order'),
            ('7', 'Produced with order to be cancelled'),
            ('8', 'Service (no material)'),
            ('9', 'Cancel product'),
            ], 'Metel State', help='Status product in METEL'),
        
        'metel_weblink': fields.function(
            _get_producer_web_link, method=True, type='char', 
            string='Weblink', multi=True), 
        'metel_weblink_image': fields.function(
            _get_producer_web_link, method=True, type='char', 
            string='Weblink image', multi=True), 
        'metel_weblink_pdf': fields.function(
            _get_producer_web_link, method=True, type='char', 
            string='Weblink PDF', multi=True), 
        }
        
    _defaults = {
        # Default value:
        'metel_state': lambda *x: '1',
        }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

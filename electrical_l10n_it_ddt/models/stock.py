# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2014 Abstract (http://www.abstract.it)
#    @author Davide Corio <davide.corio@abstract.it>
#    Copyright (C) 2014 Agile Business Group (http://www.agilebg.com)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import logging
from openerp import fields
from openerp import models
from openerp import api
from openerp import _
from openerp.exceptions import Warning
from openerp.osv import osv
from datetime import datetime, timedelta
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)

_logger = logging.getLogger(__name__)


class StockPickingCarriageCondition(models.Model):

    _name = "stock.picking.carriage_condition"
    _description = "Carriage Condition"

    name = fields.Char(string='Carriage Condition', required=True,
       translate=True)
    note = fields.Text(string='Note')


class StockPickingGoodsDescription(models.Model):

    _name = 'stock.picking.goods_description'
    _description = "Description of Goods"

    name = fields.Char(string='Description of Goods', required=True,
       translate=True)
    note = fields.Text(string='Note')


class StockPickingTransportationReason(models.Model):

    _name = 'stock.picking.transportation_reason'
    _description = 'Reason for Transportation'

    name = fields.Char(string='Reason For Transportation', required=True,
       translate=True)
    note = fields.Text(string='Note')


class StockPickingTransportationMethod(models.Model):

    _name = 'stock.picking.transportation_method'
    _description = 'Method of Transportation'

    name = fields.Char(string='Method of Transportation', required=True,
       translate=True)
    note = fields.Text(string='Note')

class StockMove(models.Model):
    _inherit = "stock.move"

    ddt_id = fields.Many2one('stock.ddt', ondelete="set null")

class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    @api.multi
    def _get_invoiced_status(self, ):
        ''' Get invoice status on account
        '''
        ddt_pool = self.env['stock.ddt']
        for account in self:
            ddts = ddt_pool.search([
                ('account_id', '=', account.id),
                ])
            if not account.total_amount:    
                account.invoices_status = 0.0
            else:    
                account.invoices_status = sum(
                    [ddt.total_amount for ddt in ddts]) / account.total_amount
    
    ddt_id = fields.Many2one('stock.ddt', ondelete="set null")
    invoiced_status = fields.Float('Invoiced status', digits=(16, 3), 
        compute=_get_invoiced_status)

class StockDdT(models.Model):

    _name = 'stock.ddt'
    _description = 'DdT'


    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    def onchange_ddt_partner_filter(self, cr, uid, ids, 
            partner_id, account_no_parent, context=None):
        ''' On change partner and check box
        '''
        if account_no_parent:
            domain = [
                ('type', 'in', ['normal', 'contract']),
                ('state', '!=', 'close'),
                ('partner_id', '=', False),
                ]
        else:        
            domain = [
                ('type', 'in', ['normal', 'contract']),
                ('state', '!=', 'close'),
                ('partner_id', '=', partner_id)
                ]
        return {'domain': {'account_id': domain, }}
        
            # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    @api.one
    def set_not_invoiced_true(self):
        self.write({'not_invoiced': True})

    @api.one
    def set_not_invoiced_false(self):
        self.write({'not_invoiced': False})

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    @api.multi
    def get_date_now(self):
        ''' 
        '''
        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        _logger.warning('DDT now: %s' % now)
        return now
        
    @api.multi
    def get_sequence(self):
        # XXX: allow config of default seq per company
        return self.env['ir.sequence'].search(
            [('code', '=', 'stock.ddt')])[0].id

    name = fields.Char(string='Number')
    date = fields.Datetime(
        required=True, 
        default=get_date_now,
        # XXX DOESN'T WORK!:
        #default=fields.Datetime.now(),
        #default=datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        )

    account_no_parent = fields.Boolean('Account without partner')
    delivery_date = fields.Datetime()
    sequence = fields.Many2one(
        'ir.sequence', string='Sequence',
        default=get_sequence, required=True)
    picking_ids = fields.One2many(
        'stock.picking', 'ddt_id', string='Pickings', readonly=True)
    ddt_lines = fields.One2many(
        'stock.move', 'ddt_id', string='DdT Line', readonly=True,
        compute='_get_lines')

    # External invoiced:
    is_invoiced = fields.Boolean('Is invoiced')    
    invoice_id = fields.Many2one(
        'account.invoice', string='Invoice', required=False)

    account_id = fields.Many2one(
        'account.analytic.account', string='Account', required=False)
    not_invoiced = fields.Boolean('Not invoiced')    
    invoice_number = fields.Char('Invoice number', size=30)
    invoice_amount = fields.Float('Invoice amount', digits=(16, 2))
    
    contact_id = fields.Many2one(
        'res.partner', string='Contact')
    partner_id = fields.Many2one(
        'res.partner', string='Partner', required=True)
    delivery_address_id = fields.Many2one(
        'res.partner', string='Delivery Address', required=False)
    carriage_condition_id = fields.Many2one(
        'stock.picking.carriage_condition', 'Carriage Condition')
    goods_description_id = fields.Many2one(
        'stock.picking.goods_description', 'Description of Goods')
    transportation_reason_id = fields.Many2one(
        'stock.picking.transportation_reason',
        'Reason for Transportation')
    transportation_method_id = fields.Many2one(
        'stock.picking.transportation_method',
        'Method of Transportation')
    carrier_id = fields.Many2one(
        'res.partner', string='Carrier')
    parcels = fields.Integer()
    note = fields.Text('Note')
    note_pre = fields.Text('Note pre')
    note_post = fields.Text('Note post')
    state = fields.Selection(
        [('draft', 'Draft'),
         ('confirmed', 'Confirmed'),
         ('cancelled', 'Cancelled')],
        string='State',
        default='draft'
    )

    def _get_lines(self):
        for ddt in self:
            for picking in ddt.picking_ids:
                ddt.ddt_lines += picking.move_lines
        
    @api.multi
    def set_number(self):
        for ddt in self:
            if not ddt.name:
                ddt.write({
                    'name': ddt.sequence.get(ddt.sequence.code),
                })

    @api.multi
    def action_confirm(self):
        self.write({'state': 'confirmed'})

    @api.multi
    def action_cancel(self):
        self.write({'state': 'cancelled'})

    @api.multi
    def action_reopen(self):
        self.write({'state': 'draft'})
        self.delete_workflow()
        self.create_workflow()
        return True

    @api.multi
    def name_get(self):
        result = []
        for ddt in self:
            result.append((ddt.id, "%s" % (ddt.name or 'N/A')))
        return result


class StockPicking(models.Model):

    _inherit = "stock.picking"

    carriage_condition_id = fields.Many2one(
        'stock.picking.carriage_condition', string='Carriage Condition')
    goods_description_id = fields.Many2one(
        'stock.picking.goods_description', string='Description of Goods')
    transportation_reason_id = fields.Many2one(
        'stock.picking.transportation_reason',
        string='Reason for Transportation')
    transportation_method_id = fields.Many2one(
        'stock.picking.transportation_method',
        string='Method of Transportation')
    parcels = fields.Integer()
    ddt_id = fields.Many2one('stock.ddt', string='DdT')
    ddt_type = fields.Selection(
        string="DdT Type", related='picking_type_id.code')        
    #invoice_id = fields.Many2one('account.invoice', string="Invoice", 
    #    related='ddt_id.invoice_id', store=False, readonly=True)
    invoice_id = fields.Many2one('account.invoice', string='Direct invoice')
    note_pre = fields.Text('Note pre')
    note_post = fields.Text('Note post')


    def action_invoice_create(
            self, cr, uid, ids, journal_id, group=False, type='out_invoice',
            context=None):
        ''' Action for create invoice from pickings (or DDT > pick > invoice)
            Note: Inherit Append DDT extra data
        '''    
        if not context:
            context = {}
        invoice_obj = self.pool['account.invoice']
        res = super(StockPicking, self).action_invoice_create(
            cr, uid, ids, journal_id, group, type, context)
            
        # TODO Use only first element?
        note_pre = ''
        note_pre_list = []
        note_post = ''
        note_post_list = []
        destination_partner_id = False
        for picking in self.browse(cr, uid, ids, context=context):
            # Pre pick + DDT (if exist)
            pre_all = (picking.ddt_text_note_pre or '').strip() or (
                picking.text_note_pre or '').strip()
            if pre_all and pre_all not in note_pre_list:
                note_pre += '%s\n' % pre_all
                note_pre_list.append(pre_all)

            # Post pick + DDT (if exist)
            post_all = (picking.ddt_text_note_post or '').strip() or (
                picking.text_note_post or '').strip()
            if post_all and post_all not in note_post_list:
                note_post += '%s\n' % post_all
                note_post_list.append(post_all)

            # TODO remove from middle of the loop and check that are all
            # equals!!!    
            if not destination_partner_id and picking.destination_partner_id:
                destination_partner_id = picking.destination_partner_id.id
            if destination_partner_id != picking.destination_partner_id.id:
                raise osv.except_osv(_('Error'), _('Different destination!'))
            invoice_obj.write(cr, uid, res, {                
                # DDT fields:
                'destination_partner_id':
                picking.destination_partner_id and
                picking.destination_partner_id.id, 
                #TODO invoice?!?!             
                'carriage_condition_id':
                picking.carriage_condition_id and
                picking.carriage_condition_id.id,
                'goods_description_id':
                picking.goods_description_id and
                picking.goods_description_id.id,
                'transportation_reason_id':
                picking.transportation_reason_id and
                picking.transportation_reason_id.id,
                'transportation_method_id':
                picking.transportation_method_id and
                picking.transportation_method_id.id,
                'parcels': picking.parcels,                
            })
        invoice_obj.write(cr, uid, res, {
            'text_note_pre': note_pre,
            'text_note_post': note_post,            
            })            
        return res

class AccountInvoice(models.Model):
    ''' Relation for invoice
    '''
    _inherit = 'account.invoice'
        
    def invoice_open_manual(self, cr, uid, ids, context=None):
        """ Button event
            @param cr: cursor to database
            @param uid: id of current user
            @param ids: list of record ids on which business flow executes
            @param context: other context
            
            @return: always return True
        """
        action_date_assign()
        #action_move_create()
        action_number()
        #invoice_validate()
        
        
        return True    
        
    ddt_ids = fields.One2many(
        'stock.ddt', 'invoice_id', string='DDT', readonly=True)


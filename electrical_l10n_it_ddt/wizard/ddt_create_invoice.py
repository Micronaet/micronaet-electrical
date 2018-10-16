# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2014 Abstract (http://www.abstract.it)
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


from openerp import models, api, fields
from openerp.tools.translate import _
from openerp.exceptions import Warning


class DdTCreateInvoice(models.TransientModel):
    ''' Wizard to create invoice from DDT open
    '''

    _name = 'ddt.create.invoice'

    # -------------------------------------------------------------------------
    # COLUMNS:
    # -------------------------------------------------------------------------
    #journal_id = fields.Many2one('account.journal', 'Journal', required=True)
    #date = fields.Date('Date')
    # Filter paremeters:
    partner_id = fields.Many2one('res.partner', 'Partner')
    account_id = fields.Many2one('account.analytic.account', 'Account')
    from_date = fields.Date('From date')
    to_date = fields.Date('To date')

    # -------------------------------------------------------------------------
    #                                 UTILITY:
    # -------------------------------------------------------------------------
    @api.model
    def filter_domain(self):
        ''' Generate domain list
        '''
        # Start: 
        domain = [
            ('ddt_id', '!=', False), # only DDT
            ('partner_id', '!=', False), # with partner
            ('ddt_id', '=', False), # not DDT
            ('invoice_id', '=', False), # not direct invoiced
            ]
        
        partner_id = self.partner_id.id
        if partner_id:
            domain.append(('partner_id', '=', partner_id))

        account_id = self.account_id.id
        if account_id:
            domain.append(('account_id', '=', account_id))

        from_date = self.from_date
        if from_date:
            domain.append(('delivery_date', '>=', '%s 00:00:00' % from_date))
        to_date = self.to_date
        if to_date:
            domain.append(('delivery_date', '<=', '%s 23:59:59' % to_date))
        return domain

    def check_ddt_data(self, ddts):
        ''' Check DDT paremeter:
        '''
        carriage_condition_id = False
        goods_description_id = False
        transportation_reason_id = False
        transportation_method_id = False
        parcels = False
        
        payment_term_id = False
        used_bank_id = False
        default_carrier_id = False
        
        for ddt in ddts:
            if (
                carriage_condition_id and
                ddt.carriage_condition_id.id != carriage_condition_id
            ):
                raise Warning(
                    _('Selected DDTs have different Carriage Conditions'))
            if (
                goods_description_id and
                ddt.goods_description_id.id != goods_description_id
            ):
                raise Warning(
                    _('Selected DDTs have different Descriptions of Goods'))
            if (
                transportation_reason_id and
                ddt.transportation_reason_id.id != transportation_reason_id
            ):
                raise Warning(
                    _('Selected DDTs have different '
                      'Reasons for Transportation'))
            if (
                transportation_method_id and
                ddt.transportation_method_id.id != transportation_method_id
            ):
                raise Warning(
                    _('Selected DDTs have different '
                      'Methods of Transportation'))
            if (
                parcels and
                ddt.parcels != parcels
            ):
                raise Warning(
                    _('Selected DDTs have different parcels'))


            if (
                payment_term_id and
                ddt.payment_term_id.id != payment_term_id
            ):
                raise Warning(
                    _('Selected DDTs have different '
                      'Payment terms'))
            if (
                used_bank_id and
                ddt.used_bank_id.id != used_bank_id
            ):
                raise Warning(
                    _('Selected DDTs have different '
                      'Bank account'))
            if (
                default_carrier_id and
                ddt.default_carrier_id.id != default_carrier_id
            ):
                raise Warning(
                    _('Selected DDTs have different '
                      'Carrier'))

    @api.multi
    def create_invoice(self):
        ''' Create invoice from selected pickings ddt
            overrided?
        '''
        # Pool used:
        ddt_model = self.env['stock.ddt']
        invoice_pool = self.pool['account.invoice']

        domain = self.filter_domain()
        
        ddts = ddt_model.filter(domain)
        if not ddts:
            raise Warning(_('No DDT selected with this filter'))
        
        ddt_db = {}
        for ddt in ddts:
            key = (ddt.partner_id, ddt.account_id)
            if key not in ddt_db:
                ddt_db[key] = []
            ddt_db[key].append(ddt)

        invoice_ids = []
        for key in ddt_db:
            partner, account = key
            
            # -----------------------------------------------------------------
            # Create new Invoice: 
            # -----------------------------------------------------------------
            # TODO manage 'out_refund'   'in_invoice'   'in_refund'
            date_invoice = fields.Date.from_string(fields.Date.now())
                
            values = {
                'partner_id': partner.id,
                'date_invoice': date_invoice,
                #'journal_id': False,
                
                'delivery_date': 
                    date_invoice,
                #'carriage_condition_id': partner.carriage_condition_id.id,
                #'goods_description_id': partner.goods_description_id.id,
                #'transportation_reason_id': 
                #    partner.transportation_reason_id.id,
                #'transportation_method_id': 
                #    partner.transportation_method_id.id, 
                }
                
            # -----------------------------------------------------------------
            # Update onchange ref (partner):    
            # -----------------------------------------------------------------
            import pdb; pdb.set_trace()
            res = invoice_pool.onchange_partner_id(
                cr, uid, False,
                'out_invoice', 
                partner.id, 
                date_invoice, 
                False,#payment_term,
                False,#partner_bank_id, 
                1, #company_id, 
                #context
                )
            values.update(res.get('value', {}))    
            
            invoice = invoice_pool.create(values)
            invoice_ids.append(invoice.id)
            
            # -----------------------------------------------------------------
            # Link DDT to new invoice:
            # -----------------------------------------------------------------
            for ddt in ddt_db[key]:
                ddt.invoice_id = invoice.id
        
        #self.check_ddt_data(ddts)
        #for ddt in ddts:
        #    for picking in ddt.picking_ids:
        #        pickings.append(picking.id)
        #        for move in picking.move_lines:
        #            if move.invoice_state != '2binvoiced':
        #                raise Warning(
        #                    _('Move %s is not invoiceable') % move.name)

        invoices = picking_pool.action_invoice_create(
            self.env.cr,
            self.env.uid,
            pickings,
            self.journal_id.id, group=True, context=None)
        invoice_obj = self.env['account.invoice'].browse(invoices)
        

        # ---------------------------------------------------------------------
        # Open Invoice:    
        # ---------------------------------------------------------------------
        ir_model_data = self.env['ir.model.data']
        form_res = ir_model_data.get_object_reference(
            'account', 'invoice_form')
        form_id = form_res and form_res[1] or False
        tree_res = ir_model_data.get_object_reference(
            'account', 'invoice_tree')
        tree_id = tree_res and tree_res[1] or False
        
        return {
            'name': 'Invoice',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'account.invoice',
            #'res_id': invoices[0],
            'view_id': tree_id,
            'views': [(tree_id, 'tree'), (form_id, 'form')],
            'type': 'ir.actions.act_window',
            }

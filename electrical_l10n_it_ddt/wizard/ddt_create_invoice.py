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
            ('partner_id', '!=', False), # with partner
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
                    ddt.payment_term_id.id != payment_term_id):
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

    def print_selection(self, cr, uid, ids, context=None):
        ''' Print selection filter
        '''
        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        ddt_pool = self.pool.get('stock.ddt')
        
        domain = self.filter_domain(cr, uid, context=context)
        
        ddt_ids = ddt_pool.search(cr, uid, domain, context=context)
        if not ddt_ids:
            raise Warning(_('No DDT selected with this filter'))
        
        # Collect data:
        ddt_db = {}
        for ddt in ddt_pool.browse(cr, uid, ddt_ids, context=context):
            key = (ddt.partner_id, ddt.account_id)
            if key not in ddt_db:
                ddt_db[key] = []
            ddt_db[key].append(ddt)
        
        # ---------------------------------------------------------------------
        #                                Excel creation:
        # ---------------------------------------------------------------------        
        # Sheet name:
        ws_names = [
            [
                'Fatture', 
                [35, 15, 30, 15, 15, 15,], 
                ['Partner', 'Fattura', 'Conto analitico', 'DDT', 'Picking', 
                    'Totale'
                    ], 
                0,
                ],
                
            [
                'Dettaglio', 
                [35, 15, 30, 15, 15, 20, 10, 10,], 
                ['Partner', 'Fattura', 'Conto analitico', 'DDT', 'Picking', 
                    'Prodotto', 'UM.', 'Q.', 'Listino', 'Subtotale', 
                    ], 
                0
                ],
            ]
        
        # ---------------------------------------------------------------------        
        # WS creation:    
        # ---------------------------------------------------------------------        
        format_load = False
        for record in ws_names:            
            ws_name, width, header, row = record

            # Create sheet:
            excel_pool.create_worksheet(ws_name)
            

            # -----------------------------------------------------------------
            # Get used format:
            # -----------------------------------------------------------------
            if not format_load:
                format_load = True
                excel_pool.get_format()
                f_title = excel_pool.get_format('title')
                f_header = excel_pool.get_format('header')
                f_text = excel_pool.get_format('text')
                f_number = excel_pool.get_format('number')

            # Setup columns
            excel_pool.column_width(ws_name, width)
            
            # Print header
            excel_pool.write_xls_line(
                ws_name, row, header, default_format=f_header)
            record[3] += 1    

        # Print data:    
        i = 0
        for key in ddt_db:
            i += 1
            partner, account = key
            data = [
                # Invoice:
                partner.name,
                '# %s' % i,
                account.name,

                # DDT:
                '', 
                
                # Picking:
                'NON PRESENTI',
                
                # Stock move:
                '',
                '',
                '',
                '',
                '',
                
                # Total,
                0.0,
                ]
            
            for ddt in ddt_db[key]:
                data[3] = ddt.name or 'NON CONFERMATA'
                for picking in ddt.picking_ids:
                    data[4] = picking.name
                    
                    # ---------------------------------------------------------
                    # Detail: 
                    # ---------------------------------------------------------
                    if picking.move_lines:                                        
                        for move in picking.move_lines:
                            try:
                                list_price = move.product_id.metel_list_price
                            except:
                                list_price = 0.0    
                            total =  list_price * move.product_qty
                            
                            data[5] = move.product_id.default_code
                            data[6] = move.product_uom.name
                            data[7] = (move.product_qty, f_number)
                            data[8] = (list_price, f_number)
                            data[9] = (total, f_number)
                            
                            data[10] += total
                            
                            excel_pool.write_xls_line(
                                ws_names[1][0], ws_names[1][3], data[:10],
                                default_format=f_text)
                            ws_names[1][3] += 1
                    else: # No movement
                        data[5] = 'NESSUN MOVIMENTO'
                        data[6] = '/'
                        data[7] = 0.0
                        data[8] = 0.0
                        data[9] = 0.0
                        
                        excel_pool.write_xls_line(
                            ws_names[1][0], ws_names[1][3], data[:10],
                            default_format=f_text)
                        ws_names[1][3] += 1
                            
                
            # -----------------------------------------------------------------
            # Summary:
            # -----------------------------------------------------------------
            summary = data[:5]
            summary.append((data[10], f_number))

            excel_pool.write_xls_line(
                ws_names[0][0], ws_names[0][3], summary,
                default_format=f_text)
            ws_names[0][3] += 1

        return excel_pool.return_attachment(
            cr, uid, 'Fatture_generate') #'invoice.xlsx')    

    @api.multi
    def create_invoice(self):
        ''' Create invoice from selected pickings ddt
            overrided?
        '''
        # Pool used:
        ddt_model = self.env['stock.ddt']
        invoice_pool = self.pool.get('account.invoice') # old

        domain = self.filter_domain()
        
        ddts = ddt_model.search(domain)
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
            # TODO manage     'out_refund'     'in_invoice'     'in_refund'
            date_invoice = fields.Date.today()
                
            values = {
                'partner_id': partner.id,
                'date_invoice': date_invoice,
                #'journal_id': False,
                
                #'delivery_date': date_invoice,
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
            res = invoice_pool.onchange_partner_id(
                self.env.cr, self.env.uid, 
                False,
                'out_invoice', 
                partner.id, 
                date_invoice, 
                False,#payment_term,
                False,#partner_bank_id, 
                1, #company_id, 
                self.env.context
                )
            values.update(res.get('value', {}))    
            
            invoice_id = invoice_pool.create(
                self.env.cr, self.env.uid, values, self.env.context)
            invoice_ids.append(invoice_id)
            
            # -----------------------------------------------------------------
            # Link DDT to new invoice:
            # -----------------------------------------------------------------
            for ddt in ddt_db[key]:
                ddt.invoice_id = invoice_id
        
        #self.check_ddt_data(ddts)
        #for ddt in ddts:
        #    for picking in ddt.picking_ids:
        #        pickings.append(picking.id)
        #        for move in picking.move_lines:
        #            if move.invoice_state != '2binvoiced':
        #                raise Warning(
        #                    _('Move %s is not invoiceable') % move.name)

        #invoices = picking_pool.action_invoice_create(
        #    self.env.cr,
        #    self.env.uid,
        #    pickings,
        #    self.journal_id.id, group=True, context=None)
        #invoice_obj = self.env['account.invoice'].browse(invoices)
        

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
            'domain': [('id', 'in', invoice_ids)],
            'type': 'ir.actions.act_window',
            }

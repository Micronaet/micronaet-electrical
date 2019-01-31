# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Francesco Apruzzese <f.apruzzese@apuliasoftware.it>
#    Copyright (C) Francesco Apruzzese
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


from openerp import fields
from openerp import models
from openerp import workflow
from openerp import api
from openerp import _
from openerp.exceptions import Warning


class DdTFromPickings(models.TransientModel):

    _name = 'ddt.from.pickings'

    # -------------------------------------------------------------------------
    #                                 COLUMNS:
    # -------------------------------------------------------------------------
    partner_id = fields.Many2one('res.partner', 'Partner')
    account_id = fields.Many2one('account.analytic.account', 'Account')
    from_date = fields.Date('From date')
    to_date = fields.Date('To date')
    auto_confirm = fields.Boolean('Auto confirm', 
        help='Auto confirm DDT when created')
    # TODO method selection for method    
    #picking_ids = fields.Many2many('stock.picking', default=_get_picking_ids)

    # -------------------------------------------------------------------------
    #                                 UTILITY:
    # -------------------------------------------------------------------------
    @api.model
    def filter_domain(self):
        ''' Generate domain list
        '''
        # Start: 
        domain = [
            ('pick_state', '=', 'delivered'), # only delivered
            ('partner_id', '!=', False), # with partner
            ('ddt_id', '=', False), # not DDT
            ('invoice_id', '=', False), # not direct invoiced
            #('pick_move', '=', 'out'), # only out
            ]
        
        partner_id = self.partner_id.id
        if partner_id:
            domain.append(('partner_id', '=', partner_id))

        account_id = self.account_id.id
        if account_id:
            domain.append(('account_id', '=', account_id))

        from_date = self.from_date
        if from_date:
            domain.append(('min_date', '>=', '%s 00:00:00' % from_date))
        to_date = self.to_date
        if to_date:
            domain.append(('min_date', '<=', '%s 23:59:59' % to_date))
        return domain        

    # -------------------------------------------------------------------------
    #                                 BUTTONS:
    # -------------------------------------------------------------------------
    def print_selection(self, cr, uid, ids, context=None):
        ''' Print selection filter
        '''
        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        picking_pool = self.pool.get('stock.picking')
        
        domain = self.filter_domain(cr, uid, context=context)
        
        picking_ids = picking_pool.search(cr, uid, domain, context=context)
        if not picking_ids:
            raise Warning(_('No picking selected with this filter'))
        
        # Collect data:
        picking_db = {}
        for picking in picking_pool.browse(
                cr, uid, picking_ids, context=context):
            key = (picking.partner_id, picking.account_id)
            if key not in picking_db:
                picking_db[key] = []
            picking_db[key].append(picking)
        
        # ---------------------------------------------------------------------
        #                                Excel creation:
        # ---------------------------------------------------------------------        
        # Sheet name:
        ws_names = [
            [
                'DDT', 
                [35, 15, 30, 15, 15, ], 
                ['Partner', 'DDT', 'Conto analitico', 'Picking'], 
                0,
                ],
                
            [
                'Dettaglio', 
                [35, 15, 30, 15, 15, 10, 10,], 
                ['Partner', 'DDT', 'Conto analitico', 'Picking', 
                    'Prodotto', 'Q.', 'UM.', 
                    #'Subtotale',
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
        for key in picking_db:
            i += 1
            partner, account = key
            data = [
                # Invoice:
                partner.name,
                '# %s' % i,
                account.name,

                # Picking:
                '',
                
                # Stock move:
                '', '', '',
                ]
            
            for picking in picking_db[key]:
                data[3] = picking.name
                
                # ---------------------------------------------------------
                # Detail: 
                # ---------------------------------------------------------
                if picking.move_lines:
                    for move in picking.move_lines:
                        data[4] = move.product_id.default_code
                        data[5] = move.product_qty
                        data[6] = move.product_uom.name
                        
                        excel_pool.write_xls_line(
                            ws_names[1][0], ws_names[1][3], data,
                            default_format=f_text)
                        ws_names[1][3] += 1
                else: # No movement
                    data[4] = 'NESSUN MOVIMENTO'
                    data[5] = '/'
                    data[6] = '/'
                    
                    excel_pool.write_xls_line(
                        ws_names[1][0], ws_names[1][3], data,
                        default_format=f_text)
                    ws_names[1][3] += 1
                        
            
                # ---------------------------------------------------------
                # Summary:
                # ---------------------------------------------------------
                excel_pool.write_xls_line(
                    ws_names[0][0], ws_names[0][3], data[:4], 
                    default_format=f_text)
                ws_names[0][3] += 1
               

        return excel_pool.return_attachment(
            cr, uid, 'Consegne_generate') #'invoice.xlsx')    

    @api.multi
    def create_ddt(self):
        ''' Select depend on partner and create DDT from pickings
        '''
        # Pool used:        
        picking_pool = self.env['stock.picking']
        ddt_pool = self.env['stock.ddt']
        ir_model_data = self.env['ir.model.data']
                
        # Get domain clause:
        domain = self.filter_domain()
        
        # Get other parameters:
        auto_confirm = self.auto_confirm
        #method = self.method
            
        pickings = picking_pool.search(domain)
        if not pickings:
            raise Warning(_('No pick out selected with this filter'))
        
        picking_db = {}
        for picking in pickings:
            key = (picking.partner_id, picking.account_id)
            if key not in picking_db:
                picking_db[key] = []
            picking_db[key].append(picking)

        ddt_ids = []
        for key in picking_db:
            partner, account = key
            
            # Create new DDT:                     
            values = {
                'account_id': account.id,
                'delivery_date': 
                    fields.Datetime.from_string(fields.Datetime.now()),
                'partner_id': partner.id,
                'parcels': 0,
                'carriage_condition_id': partner.carriage_condition_id.id,
                'goods_description_id': partner.goods_description_id.id,
                'transportation_reason_id': 
                    partner.transportation_reason_id.id,
                'transportation_method_id': 
                    partner.transportation_method_id.id, 
                #'payment_term_id': partner.payment_term_id.id,
                #'used_bank_id': False,
                #'default_carrier_id': False,
                #'destination_partner_id': False,
                #'invoice_partner_id': False,
                }

            ddt = ddt_pool.create(values)
            ddt_ids.append(ddt.id)
            
            # Link picking to document:            
            for picking in picking_db[key]:
                picking.ddt_id = ddt.id

        
        # ---------------------------------------------------------------------
        # Workflow action if request:
        # ---------------------------------------------------------------------
        if auto_confirm:
            workflow.trg_validate(
                        uid, 'stock.ddt', ddt_id, 'ddt_confirm', cr)            

        # ---------------------------------------------------------------------
        # Show new DDTs:
        # ---------------------------------------------------------------------
        form_res = ir_model_data.get_object_reference(
            'electrical_l10n_it_ddt', 'stock_ddt_form')
        form_id = form_res and form_res[1] or False
        tree_res = ir_model_data.get_object_reference(
            'electrical_l10n_it_ddt', 'stock_ddt_tree')
        tree_id = tree_res and tree_res[1] or False


        return {
            'name': 'DdT',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'stock.ddt',
            #'res_id': ddt.id,
            'view_id': tree_id,
            'views': [(tree_id, 'tree'),(form_id, 'form')],
            'domain': [('id', 'in', ddt_ids)],
            'type': 'ir.actions.act_window',
            }

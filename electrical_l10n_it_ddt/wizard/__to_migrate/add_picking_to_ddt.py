# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Nicola Malcontenti Agile Business Group
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
from openerp import api
from openerp import _
from openerp.exceptions import Warning


class AddPickingToDdt(models.TransientModel):

    _name = "add.pickings.to.ddt"

    ddt_id = fields.Many2one('stock.ddt')

    @api.multi
    def add_to_ddt(self):
        pickings = self.env['stock.picking'].browse(
            self.env.context['active_ids'])
        for picking in pickings:
            if picking.ddt_id:
                raise Warning(
                    _("Pickings already in ddt"))
            elif picking.partner_id != self.ddt_id.partner_id:
                raise Warning(
                    _("Selected Pickings have different Partner"))
            elif picking.partner_id != self.ddt_id.partner_id:
                raise Warning(
                    _("Selected Pickings have different Partner"))
            elif picking.destination_partner_id != \
                    self.ddt_id.destination_partner_id:
                raise Warning(
                    _("Selected Pickings have different Destination"))
            #elif picking.sale_id.parcels != self.ddt_id.parcels:
            #    raise Warning(
            #        _("Selected Pickings have different parcels"))
            #elif picking.sale_id.carriage_condition_id != (
            #        self.ddt_id.carriage_condition_id):
            #    raise Warning(
            #        _("Selected Pickings have"
            #          " different carriage condition"))
            #elif picking.sale_id.goods_description_id != (
            #        self.ddt_id.goods_description_id):
            #    raise Warning(
            #        _("Selected Pickings have "
            #          "different goods description"))
            #elif picking.sale_id.transportation_reason_id != (
            #        self.ddt_id.transportation_reason_id):
            #    raise Warning(
            #        _("Selected Pickings have"
            #          " different transportation reason"))
            #elif picking.sale_id.transportation_method_id != (
            #        self.ddt_id.transportation_method_id):
            #    raise Warning(
            #        _("Selected Pickings have"
            #          " different transportation reason"))
            picking.ddt_id = self.ddt_id
        ir_model_data = self.env['ir.model.data']
        form_res = ir_model_data.get_object_reference(
            'electrical_l10n_it_ddt',
            'stock_ddt_form')
        form_id = form_res and form_res[1] or False
        tree_res = ir_model_data.get_object_reference(
            'electrical_l10n_it_ddt',
            'stock_ddt_tree')
        tree_id = tree_res and tree_res[1] or False
        return {
            'name': 'DdT',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'stock.ddt',
            'res_id': self.ddt_id.id,
            'view_id': False,
            'views': [(form_id, 'form'), (tree_id, 'tree')],
            'type': 'ir.actions.act_window',
            }

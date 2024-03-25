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
import pdb
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


class LoadElectricalProductKitWizard(orm.TransientModel):
    """ Wizard load component
    """
    _name = 'load.electrical.product.kit.wizard'

    def action_load_kit_item(self, cr, uid, ids, context=None):
        """ Update generator with component data
        """
        line_pool = self.pool.get('sale.order.line')
        move_pool = self.pool.get('stock.move')

        if not context:
            context = {}

        # Read wizart data:
        wizard = self.browse(cr, uid, ids, context=context)
        kit = wizard.kit_id
        quantity = wizard.quantity

        order = wizard.order_id
        picking = wizard.picking_id

        if order:
            return True
        # ---------------------------------------------------------------------
        # Picking mode (stock.move):
        # ---------------------------------------------------------------------
        if picking:
            picking_id = picking.id
            partner_id = picking.partner_id.id
            picking_type = picking.picking_type_id
            picking_type_id = picking_type.id
            default_location_src_id = picking_type.default_location_src_id.id
            default_location_dest_id = picking_type.default_location_dest_id.id

            for component in kit.product_ids:
                product = component.product_id
                product_id = product.id
                move_quantity = quantity * component.quantity

                # Generate line stock move in picking:
                data = move_pool.onchange_product_id(
                    cr, uid, ids,
                    product_id=product_id,
                    loc_id=default_location_src_id,
                    loc_dest_id=default_location_dest_id,
                    partner_id=partner_id).get('value', {})
                data.update({
                    'picking_id': picking_id,
                    'product_uom_qty': move_quantity,
                    'product_id': product_id,
                    'picking_type_id': picking_type_id,
                    'price_unit': product.standard_price,
                })
                move_pool.create(cr, uid, data, context=context)

            return True
        _logger.error('No document passed!')

    def onchange_kit_quantity(
            self, cr, uid, ids, kit_id, quantity, context=None):
        """ Generate a preview form
        """
        kit_pool = self.pool.get('electrical.product.kit')

        res = {}
        if not(kit_id and quantity > 0):
            return res
        kit = kit_pool.browse(cr, uid, kit_id, context=context)

        lines = '<tr><th>Q.</th><th>Codice</th><th>Componente</th></tr>'

        for component in kit.product_ids:
            lines += '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                component.quantity * quantity,
                component.product_id.default_code,
                component.product_id.name,
            )
        res['value'] = {
            'detail':
                '<table width="90%%" '
                'class="table table-condensed table-bordered">'
                '%s'
                '</table>' % lines,
        }
        return res

    _columns = {
        'order_id': fields.many2one('sale.order', 'Ordine'),
        'picking_id': fields.many2one('stock.picking', 'Picking'),
        'kit_id': fields.many2one(
            'electrical.product.kit', 'Kit', required=True),
        'quantity': fields.integer('Q.', required=True),
        'detail': fields.text('Dettagli'),
        }

    _defaults = {
        'quantity': lambda *x: 1,
        }

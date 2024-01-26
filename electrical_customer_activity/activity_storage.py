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


class ResPartnerActivityFolder(orm.Model):
    """ Model name: Res Partner Folder
    """

    _name = 'res.partner.activity.folder'
    _description = 'Activity folder'
    _order = 'name'

    _columns = {
        'name': fields.char('Nome'),
        'note': fields.text('Note'),
        'path': fields.char(
            'Percorso', size=60,
            help='Utilizzare path formato Linux File system, es.'
                 '/home/odoo/filestore oppure'
                 '~/filestore'),
        }


class ResPartnerActivityFilename(orm.Model):
    """ Model name: Res Partner File
    """

    _name = 'res.partner.activity.filename'
    _description = 'Activity template filename'
    _order = 'name'

    _columns = {
        'code': fields.char('Codice', required=True),
        'name': fields.char('Nome', required=True),
        'folder_id': fields.many2one(
            'res.partner.activity.folder', 'Cartella base', required=True),
        'filename': fields.char(
            'Nome file', required=True, size=200,
            help='Utilizzare path formato Linux File system unito ad alcuni'
                 'parametri disponibili, il percoro parte dalla cartella '
                 'di base, es.'
                 '{year}/{month}/{customer}_complete_report.xlsx '
                 'il programma sostituirà le parti e il nome file diventerà:'
                 '/home/odoo/filestore/2024/01/ROSSI_complete_report.xlsx'
                 ),
        'note': fields.text('Note'),
        }


class ResPartnerActivityStorageStage(orm.Model):
    """ Model name: Res Partner Activity Storage
    """

    _name = 'res.partner.activity.storage.stage'
    _description = 'Activity storage stage'
    _order = 'name'

    _columns = {
        'name': fields.char('Nome'),
        'note': fields.text('Note'),
        }


class ResPartnerActivityStorage(orm.Model):
    """ Model name: Res Partner Activity Storage
    """

    _name = 'res.partner.activity.storage'
    _description = 'Activity storage'
    _order = 'name desc, partner_id, account_id'

    # Button to open list:
    def generate_report_complete(self, cr, uid, ids, context=None):
        """ Generate report complete
        """
        def clean_name_path(name):
            """ Clean not used character
            """
            name = (name or '').strip()
            name = name.replace('/', '-')
            return name

        file_pool = self.pool.get('res.partner.activity.filename')
        wizard_pool = self.pool.get('res.partner.activity.wizard')

        file_ids = file_pool.search(cr, uid, [
            ('code', '=', 'ACTIVITY'),
        ], context=context)
        if not file_ids:
            raise osv.except_osv(
                _('Errore'),
                _('Impossibile generare un file, impostare nei modelli di '
                  'file un template con codice ACTIVITY per continuare!'),
            )
        file = file_pool.browse(cr, uid, file_ids, context=context)[0]
        template_name = os.path.join(
            os.path.expanduser(file.folder_id.path),
            file.filename,
        )

        for store in self.browse(cr, uid, ids, context=context):
            name = store.name
            customer = clean_name_path(store.partner_id.name)
            account = clean_name_path(store.account_id.name)
            contact = clean_name_path(store.contact_id.name)
            year = store.name[:4]
            month = store.name[-2:]

            fullname = template_name.format(
                name=name,
                customer=customer,
                account=account,
                contact=contact,
                year=year,
                month=month)

            folder = os.path.dirname(fullname)
            filename = os.path.basename(fullname)
            _logger.info('Creating report: %s' % fullname)
            try:
                os.system('mkdir -p "%s"' % folder)
                os.system('touch "%s"' % fullname)
            except:
                raise osv.except_osv(
                    _('Errore'),
                    _('Impossibile creare il percorso %s!'
                      'Probabilmente vanno puliti dei caratteri.' % fullname),
                )

            # Generate Wizard for print report:
            data = self.get_wizard_setup_data(store, mode='')
            wizard_id = wizard_pool.create(cr, uid, data, context=context)

            # Run Print button in wizard force save as filename:
            ctx = context.copy()
            ctx['save_fullname'] = fullname
            wizard_pool.action_print(cr, uid, [wizard_id], context=ctx)
        return True

    def get_wizard_setup_data(self, store, mode='default'):
        """ Generate wizard data for open or generate report
            mode = '' or 'default'
        """
        if mode:
            mode = '%s_' % mode

        return {
            '%smode' % mode: 'complete',

            '%sfrom_date' % mode: store.from_date,
            '%sto_date' % mode: store.to_date,

            '%spartner_id' % mode: store.partner_id.id,
            '%saccount_id' % mode: store.account_id.id,
            '%scontact_id' % mode: store.contact_id.id,

            '%spicking_mode' % mode: 'all',
            '%sddt_mode' % mode: 'all',  # 'ddt',  # Not invoiced (not all!)
            '%sintervent_mode' % mode: 'all',  # 'pending',
            '%sactivity_price' % mode: 'lst_price',
        }

    def open_wizard(self, cr, uid, ids, context=None):
        """ Open wizard
        """
        if context is None:
            context = {}

        store = self.browse(cr, uid, ids, context=context)[0]
        context.update(self.get_wizard_setup_data(store))

        form_view_id = False
        # tree_view_id = model_pool.get_object_reference(
        #    cr, uid,
        #    'intervention_report',
        #    'view_hr_analytic_timesheet_tree',
        #     )[1]

        return {
            'type': 'ir.actions.act_window',
            'name': 'Wizard per report',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': False,
            'res_model': 'res.partner.activity.wizard',
            'view_id': form_view_id,
            'views': [(form_view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'new',
            'nodestroy': False,
            }

    def get_total_intervent_draft(self, cr, uid, ids, context=None):
        """ Open Intervent not invoiced
        """
        if context is None:
            context = {}

        model_pool = self.pool.get('ir.model.data')
        intervent_pool = self.pool.get('hr.analytic.timesheet')

        store = self.browse(cr, uid, ids, context=context)[0]
        domain = [
            ('date_start', '>=', store.from_date),
            ('date_start', '<=', store.to_date),
            ('intervent_partner_id', '=', store.partner_id.id),
            ('intervent_contact_id', '=', store.contact_id.id),
            ('account_id', '=', store.account_id.id),
            ]
        if context.get('is_invoiced'):
            domain.append(('is_invoiced', '=', True))
            name = 'Interventi fatturati'
        else:
            domain.append(('is_invoiced', '=', False))
            name = 'Interventi da fatture'

        record_ids = intervent_pool.search(cr, uid, domain, context=context)
        tree_view_id = model_pool.get_object_reference(
            cr, uid,
            'intervention_report',
            'view_hr_analytic_timesheet_tree',
            )[1]

        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'view_type': 'form',
            'view_mode': 'tree,form',
            # 'res_id': ids[0],
            'res_model': 'hr.analytic.timesheet',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (False, 'form')],
            'domain': [('id', 'in', record_ids)],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    def get_total_intervent_invoice(self, cr, uid, ids, context=None):
        """ Open Intervent invoiced (call original button)
        """
        if context is None:
            context = {}

        context['is_invoiced'] = True
        return self.get_total_intervent_draft(cr, uid, ids, context=context)

    def get_total_picking(self, cr, uid, ids, context=None):
        """ Open Picking
        """
        model_pool = self.pool.get('ir.model.data')
        store = self.browse(cr, uid, ids, context=context)[0]

        picking_pool = self.pool.get('stock.picking')
        domain = [
            ('min_date', '>=', '%s 00:00:00' % store.from_date),
            ('min_date', '<=', '%s 23:59:59' % store.to_date),
            ('ddt_id', '=', False),  # Not DDT
            ('pick_move', '=', 'out'),  # Only out movement

            ('partner_id', '=', store.partner_id.id),
            ('contact_id', '=', store.contact_id.id),
            ('account_id', '=', store.account_id.id),
        ]
        record_ids = picking_pool.search(cr, uid, domain, context=context)
        tree_view_id = model_pool.get_object_reference(
            cr, uid,
            'fast_stock_move',
            'view_stock_picking_inline_moves_tree_fast',
            )[1]

        return {
            'type': 'ir.actions.act_window',
            'name': 'Picking aperti',
            'view_type': 'form',
            'view_mode': 'tree,form',
            # 'res_id': ids[0],
            'res_model': 'stock.picking',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (False, 'form')],
            'domain': [('id', 'in', record_ids)],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    def get_total_ddt_draft(self, cr, uid, ids, context=None):
        """ Open DDT not invoiced
        """
        model_pool = self.pool.get('ir.model.data')
        store = self.browse(cr, uid, ids, context=context)[0]

        ddt_pool = self.pool.get('stock.ddt')

        domain = [
            ('delivery_date', '>=', '%s 00:00:00' % store.from_date),
            ('delivery_date', '<=', '%s 23:59:59' % store.to_date),

            ('partner_id', '=', store.partner_id.id),
            ('contact_id', '=', store.contact_id.id),
            ('account_id', '=', store.account_id.id),
            ]
        if context.get('is_invoiced'):
            domain.append(('is_invoiced', '=', True))
        else:
            domain.append(('is_invoiced', '=', False))

        ddt_delivery_ids = set(
            ddt_pool.search(cr, uid, domain, context=context))

        domain = [
            ('date', '>=', '%s 00:00:00' % store.from_date),
            ('date', '<=', '%s 23:59:59' % store.to_date),

            ('partner_id', '=', store.partner_id.id),
            ('contact_id', '=', store.contact_id.id),
            ('account_id', '=', store.account_id.id),
            ]
        if context.get('is_invoiced'):
            domain.append(('is_invoiced', '=', True))
        else:
            domain.append(('is_invoiced', '=', False))

        ddt_date_ids = set(
            ddt_pool.search(cr, uid, domain, context=context))
        record_ids = tuple(ddt_delivery_ids | ddt_date_ids)

        tree_view_id = model_pool.get_object_reference(
            cr, uid, 'electrical_l10n_it_ddt', 'stock_ddt_tree',
            )[1]

        return {
            'type': 'ir.actions.act_window',
            'name': 'DDT da fatturare',
            'view_type': 'form',
            'view_mode': 'tree,form',
            # 'res_id': ids[0],
            'res_model': 'stock.ddt',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (False, 'form')],
            'domain': [('id', 'in', record_ids)],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    def get_total_ddt_invoice(self, cr, uid, ids, context=None):
        """ Open DDT invoiced
        """
        if context is None:
            context = {}

        context['is_invoiced'] = True
        return self.get_total_ddt_draft(cr, uid, ids, context=context)

    def get_total_invoice(self, cr, uid, ids, context=None):
        """ Open Invoice
        """
        model_pool = self.pool.get('ir.model.data')
        store = self.browse(cr, uid, ids, context=context)[0]

        invoice_pool = self.pool.get('account.invoice')
        return True

    _columns = {
        'name': fields.char('Mese', size=8, required=True),
        'note': fields.text('Note'),
        'from_date': fields.date('Dalla data'),
        'to_date': fields.date('Alla data'),

        'partner_id': fields.many2one('res.partner', 'Cliente'),
        'contact_id': fields.many2one('res.partner', 'Contatto'),
        'account_id': fields.many2one(
            'account.analytic.account', 'Commessa'),
        'stage_id': fields.many2one(
            'res.partner.activity.storage.stage', 'Stato'),

        # Check:
        # 'check_intervent': fields.boolean('Interventi'),
        # 'check_stock': fields.boolean('Consegne'),
        # 'check_ddt': fields.boolean('DDT'),
        # 'check_invoice': fields.boolean('Fatture'),

        # Detail:
        'total_intervent_draft': fields.integer('# Int. da fatt.'),
        'total_intervent_invoice': fields.integer('# Int. fatt.'),
        'total_picking': fields.integer('# Pick. da fatt.'),
        'total_ddt_draft': fields.integer('# DDT da fatt.'),
        'total_ddt_invoice': fields.integer('# DDT fatt.'),
        'total_invoice': fields.integer('# Fatture'),

        # Amount:
        'amount_intervent': fields.float('Tot. Interventi', digits=(16, 2)),
        'amount_picking': fields.float('Tot. Consegnato', digits=(16, 2)),
        'amount_ddt': fields.float('Tot. DDT', digits=(16, 2)),
        'amount_invoice': fields.float('Tot. Fatturato', digits=(16, 2)),
        }



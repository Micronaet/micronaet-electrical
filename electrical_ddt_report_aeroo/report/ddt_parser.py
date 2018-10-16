#!/usr/bin/python
# -*- coding: utf-8 -*-
##############################################################################
#
#   Copyright (C) 2010-2012 Associazione OpenERP Italia
#   (<http://www.openerp-italia.org>).
#   Copyright(c)2008-2010 SIA "KN dati".(http://kndati.lv) All Rights Reserved.
#                   General contacts <info@kndati.lv>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import os
import sys
import logging
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)


class Parser(report_sxw.rml_parse):
    counters = {}
    headers = {}
    
    def __init__(self, cr, uid, name, context):        
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_address': self.get_address,
            'get_extra_data': self.get_extra_data,
            'get_partner_list': self.get_partner_list,
            'get_vector_data': self.get_vector_data,
            'theres_partner_ref': self.theres_partner_ref,
            'get_headers': self.get_headers,
            
            # Utility:
            'report_init_reset':  self.report_init_reset,
            'get_partic_description': self.get_partic_description,
        })
        
    def get_vector_data(self, o): 
        ''' Reset parameter used in report 
        '''
        # TODO keep in a common place with DDT one's
        if o.force_vector:
            return o.force_vector or ''
        elif o.default_carrier_id and o.default_carrier_id.partner_id:
            partner = o.default_carrier_id.partner_id
            return '''%s\n%s\n%s %s %s\nP.IVA: %s Tel.: %s\nN. Albo Trasp.: %s''' % (
                    partner.name or '',
                    partner.street or '',
                    partner.zip or '',
                    partner.city or '',
                    partner.state_id.code or '',
                    partner.vat or '',
                    partner.phone or '',                
                    (partner.transport_number or '') if \
                        partner.is_vector else '',
                    )                
        else:
            return ''            
        
    def report_init_reset(self): 
        ''' Reset parameter used in report 
        '''
        self.headers = {
            'order': '', # NOTE: set up as '' for not print if empty!
            'ddt': '',
            }
            
        self.counters = {}
        return ''
        
    def get_headers(self, ref='order'):
        ''' Returs header dict
        '''
        return self.headers.get(ref, '')
        
    def theres_partner_ref(self, picking_id, ref='order'):
        ''' Get sale order reference for picking_proxy if as previous nothing)
        '''
        # Get value:
        if picking_id.name:
            # Sale ref.:
            res = _('Rif. %s') % picking_id.name
        else:        
            res = '' # _('No reference')

        # Print only first line:
        if self.headers.get(ref, False) == res:
            return False
        else:    
            self.headers[ref] = res # save for next call
            return True

    def get_partner_list(self, o):
        ''' Get list of partner address, depend on extra_field value
        '''
        res = [o.partner_id]
        if o.extra_address in ('contact', 'partner') and o.partner_ids:
            res.extend(o.partner_ids)
        return res

    def get_address(self, partner_proxy):
        ''' Get partner address with passed browse obj
        '''
        return "%s - %s - %s" % (
            partner_proxy.street or '',
            partner_proxy.zip or '',
            partner_proxy.city or '',
            )

    def get_extra_data(self, partner_proxy):
        ''' Get partner extra data with passed browse obj
        '''
        return "Phone: %s\nFax: %s\nE-mail: %s\n%s" % (
            partner_proxy.phone or '',
            partner_proxy.fax or '',
            partner_proxy.email or '',
            "%s%s" % (
                "P.IVA: %s\n" % (
                    partner_proxy.vat if partner_proxy.vat else ""),
                "C.F.: %s" % (
                    partner_proxy.fiscalcode if partner_proxy.fiscalcode else ""), )
            )

    def get_partic_description(self, partner_id, product_id):
        ''' Check if partner has partic description
        '''
        # TODO optimize
        partic_pool = self.pool.get('res.partner.product.partic')
        res = ''
        partic_ids = partic_pool.search(self.cr, self.uid, [
            ('product_id', '=', product_id),
            ('partner_id', '=', partner_id),
            ])
        if not partic_ids:
            return res
            
        partic_proxy = partic_pool.browse(self.cr, self.uid, partic_ids)[0]
        res = '%s %s' % (
            partic_proxy.partner_code or '', 
            partic_proxy.partner_description or '',
            )
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

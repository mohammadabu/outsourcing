# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.exceptions import AccessError


class Digest(models.Model):
    _inherit = 'digest.digest'

    kpi_outsourcing_task_opened = fields.Boolean('Open Tasks')
    kpi_outsourcing_task_opened_value = fields.Integer(compute='_compute_outsourcing_task_opened_value')

    def _compute_outsourcing_task_opened_value(self):
        if not self.env.user.has_group('outsourcing.group_outsourcing_user'):
            raise AccessError(_("Do not have access, skip this data for user's digest email"))
        for record in self:
            start, end, company = record._get_kpi_compute_parameters()
            record.kpi_outsourcing_task_opened_value = self.env['outsourcing.task'].search_count([
                ('stage_id.fold', '=', False),
                ('create_date', '>=', start),
                ('create_date', '<', end),
                ('company_id', '=', company.id)
            ])

    def compute_kpis_actions(self, company, user):
        res = super(Digest, self).compute_kpis_actions(company, user)
        res['kpi_outsourcing_task_opened'] = 'outsourcing.open_view_outsourcing_all&menu_id=%s' % self.env.ref('outsourcing.menu_main_pm').id
        return res

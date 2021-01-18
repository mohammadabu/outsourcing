# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'
    _description = 'Analytic Account'

    outsourcing_ids = fields.One2many('outsourcing.outsourcing', 'analytic_account_id', string='outsourcings')
    outsourcing_count = fields.Integer("outsourcing Count", compute='_compute_outsourcing_count')

    @api.depends('outsourcing_ids')
    def _compute_outsourcing_count(self):
        outsourcing_data = self.env['outsourcing.outsourcing'].read_group([('analytic_account_id', 'in', self.ids)], ['analytic_account_id'], ['analytic_account_id'])
        mapping = {m['analytic_account_id'][0]: m['analytic_account_id_count'] for m in outsourcing_data}
        for account in self:
            account.outsourcing_count = mapping.get(account.id, 0)

    @api.constrains('company_id')
    def _check_company_id(self):
        for record in self:
            if record.company_id and not all(record.company_id == c for c in record.outsourcing_ids.mapped('company_id')):
                raise UserError(_('You cannot change the company of an analytical account if it is related to a outsourcing.'))

    def unlink(self):
        outsourcings = self.env['outsourcing.outsourcing'].search([('analytic_account_id', 'in', self.ids)])
        has_tasks = self.env['outsourcing.task'].search_count([('outsourcing_id', 'in', outsourcings.ids)])
        if has_tasks:
            raise UserError(_('Please remove existing tasks in the outsourcing linked to the accounts you want to delete.'))
        return super(AccountAnalyticAccount, self).unlink()

    def action_view_outsourcings(self):
        kanban_view_id = self.env.ref('outsourcing.view_outsourcing_kanban').id
        result = {
            "type": "ir.actions.act_window",
            "res_model": "outsourcing.outsourcing",
            "views": [[kanban_view_id, "kanban"], [False, "form"]],
            "domain": [['analytic_account_id', '=', self.id]],
            "context": {"create": False},
            "name": "outsourcings",
        }
        if len(self.outsourcing_ids) == 1:
            result['views'] = [(False, "form")]
            result['res_id'] = self.outsourcing_ids.id
        return result

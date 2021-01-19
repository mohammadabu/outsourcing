# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    """ Inherits partner and adds Tasks information in the partner form """
    _inherit = 'res.partner'

    task_ids = fields.One2many('outsourcing.task', 'partner_id', string='Tasks')
    task_count = fields.Integer(compute='_compute_task_count', string='# Tasks')

    def _compute_task_count(self):
        fetch_data = self.env['outsourcing.task'].read_group([('partner_id', 'in', self.ids)], ['partner_id'], ['partner_id'])
        result = dict((data['partner_id'][0], data['partner_id_count']) for data in fetch_data)
        for partner in self:
            partner.task_count = result.get(partner.id, 0) + sum(c.task_count for c in partner.child_ids)


class res_users_rule(models.Model):
    _name = 'res.users'
    _inherit = 'res.users'

    project_rule = fields.Many2many(compute='_task_rule_calc', comodel_name='outsourcing.outsourcing')
    def _task_rule_calc(self):
        stage_ids = []
        for rec in self:
            rec.project_rule = stage_ids

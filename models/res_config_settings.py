# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_outsourcing_forecast = fields.Boolean(string="Forecasts")
    module_hr_timesheet = fields.Boolean(string="Task Logs")
    group_subtask_outsourcing = fields.Boolean("Sub-tasks", implied_group="outsourcing.group_subtask_outsourcing")
    group_outsourcing_rating = fields.Boolean("Use Rating on outsourcing", implied_group='outsourcing.group_outsourcing_rating')

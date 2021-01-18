# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.misc import format_date


class outsourcingTaskType(models.Model):
    _name = 'outsourcing.task.type'
    _description = 'Task Stage'
    _order = 'sequence, id'

    def _get_default_outsourcing_ids(self):
        default_outsourcing_id = self.env.context.get('default_outsourcing_id')
        return [default_outsourcing_id] if default_outsourcing_id else None

    name = fields.Char(string='Stage Name', required=True, translate=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=1)
    outsourcing_ids = fields.Many2many('outsourcing.outsourcing', 'outsourcing_task_type_rel', 'type_id', 'outsourcing_id', string='outsourcings',
        default=_get_default_outsourcing_ids)
    legend_blocked = fields.Char(
        'Red Kanban Label', default=lambda s: _('Blocked'), translate=True, required=True,
        help='Override the default value displayed for the blocked state for kanban selection, when the task or issue is in that stage.')
    legend_done = fields.Char(
        'Green Kanban Label', default=lambda s: _('Ready for Next Stage'), translate=True, required=True,
        help='Override the default value displayed for the done state for kanban selection, when the task or issue is in that stage.')
    legend_normal = fields.Char(
        'Grey Kanban Label', default=lambda s: _('In Progress'), translate=True, required=True,
        help='Override the default value displayed for the normal state for kanban selection, when the task or issue is in that stage.')
    mail_template_id = fields.Many2one(
        'mail.template',
        string='Email Template',
        domain=[('model', '=', 'outsourcing.task')],
        help="If set an email will be sent to the customer when the task or issue reaches this step.")
    fold = fields.Boolean(string='Folded in Kanban',
        help='This stage is folded in the kanban view when there are no records in that stage to display.')
    rating_template_id = fields.Many2one(
        'mail.template',
        string='Rating Email Template',
        domain=[('model', '=', 'outsourcing.task')],
        help="If set and if the outsourcing's rating configuration is 'Rating when changing stage', then an email will be sent to the customer when the task reaches this step.")
    auto_validation_kanban_state = fields.Boolean('Automatic kanban status', default=False,
        help="Automatically modify the kanban state when the customer replies to the feedback for this stage.\n"
            " * A good feedback from the customer will update the kanban state to 'ready for the new stage' (green bullet).\n"
            " * A medium or a bad feedback will set the kanban state to 'blocked' (red bullet).\n")

    def unlink(self):
        stages = self
        default_outsourcing_id = self.env.context.get('default_outsourcing_id')
        if default_outsourcing_id:
            shared_stages = self.filtered(lambda x: len(x.outsourcing_ids) > 1 and default_outsourcing_id in x.outsourcing_ids.ids)
            tasks = self.env['outsourcing.task'].with_context(active_test=False).search([('outsourcing_id', '=', default_outsourcing_id), ('stage_id', 'in', self.ids)])
            if shared_stages and not tasks:
                shared_stages.write({'outsourcing_ids': [(3, default_outsourcing_id)]})
                stages = self.filtered(lambda x: x not in shared_stages)
        return super(outsourcingTaskType, stages).unlink()


class outsourcing(models.Model):
    _name = "outsourcing.outsourcing"
    _description = "outsourcing"
    _inherit = ['portal.mixin', 'mail.alias.mixin', 'mail.thread', 'rating.parent.mixin']
    _order = "sequence, name, id"
    _period_number = 5
    _rating_satisfaction_days = False  # takes all existing ratings
    _check_company_auto = True

    def get_alias_model_name(self, vals):
        return vals.get('alias_model', 'outsourcing.task')

    def get_alias_values(self):
        values = super(outsourcing, self).get_alias_values()
        values['alias_defaults'] = {'outsourcing_id': self.id}
        return values

    def _compute_attached_docs_count(self):
        Attachment = self.env['ir.attachment']
        for outsourcing in self:
            outsourcing.doc_count = Attachment.search_count([
                '|',
                '&',
                ('res_model', '=', 'outsourcing.outsourcing'), ('res_id', '=', outsourcing.id),
                '&',
                ('res_model', '=', 'outsourcing.task'), ('res_id', 'in', outsourcing.task_ids.ids)
            ])

    def _compute_task_count(self):
        task_data = self.env['outsourcing.task'].read_group([('outsourcing_id', 'in', self.ids), '|', ('stage_id.fold', '=', False), ('stage_id', '=', False)], ['outsourcing_id'], ['outsourcing_id'])
        result = dict((data['outsourcing_id'][0], data['outsourcing_id_count']) for data in task_data)
        for outsourcing in self:
            outsourcing.task_count = result.get(outsourcing.id, 0)

    def attachment_tree_view(self):
        attachment_action = self.env.ref('base.action_attachment')
        action = attachment_action.read()[0]
        action['domain'] = str([
            '|',
            '&',
            ('res_model', '=', 'outsourcing.outsourcing'),
            ('res_id', 'in', self.ids),
            '&',
            ('res_model', '=', 'outsourcing.task'),
            ('res_id', 'in', self.task_ids.ids)
        ])
        action['context'] = "{'default_res_model': '%s','default_res_id': %d}" % (self._name, self.id)
        return action

    @api.model
    def activate_sample_outsourcing(self):
        """ Unarchives the sample outsourcing 'outsourcing.outsourcing_outsourcing_data' and
            reloads the outsourcing dashboard """
        # Unarchive sample outsourcing
        outsourcing = self.env.ref('outsourcing.outsourcing_outsourcing_data', False)
        if outsourcing:
            outsourcing.write({'active': True})

        cover_image = self.env.ref('outsourcing.msg_task_data_14_attach', False)
        cover_task = self.env.ref('outsourcing.outsourcing_task_data_14', False)
        if cover_image and cover_task:
            cover_task.write({'displayed_image_id': cover_image.id})

        # Change the help message on the action (no more activate outsourcing)
        action = self.env.ref('outsourcing.open_view_outsourcing_all', False)
        action_data = None
        if action:
            action.sudo().write({
                "help": _('''<p class="o_view_nocontent_smiling_face">
                    Create a new outsourcing</p>''')
            })
            action_data = action.read()[0]
        # Reload the dashboard
        return action_data

    def _compute_is_favorite(self):
        for outsourcing in self:
            outsourcing.is_favorite = self.env.user in outsourcing.favorite_user_ids

    def _inverse_is_favorite(self):
        favorite_outsourcings = not_fav_outsourcings = self.env['outsourcing.outsourcing'].sudo()
        for outsourcing in self:
            if self.env.user in outsourcing.favorite_user_ids:
                favorite_outsourcings |= outsourcing
            else:
                not_fav_outsourcings |= outsourcing

        # outsourcing User has no write access for outsourcing.
        not_fav_outsourcings.write({'favorite_user_ids': [(4, self.env.uid)]})
        favorite_outsourcings.write({'favorite_user_ids': [(3, self.env.uid)]})

    def _get_default_favorite_user_ids(self):
        return [(6, 0, [self.env.uid])]

    name = fields.Char("Name", index=True, required=True, tracking=True)
    active = fields.Boolean(default=True,
        help="If the active field is set to False, it will allow you to hide the outsourcing without removing it.")
    sequence = fields.Integer(default=10, help="Gives the sequence order when displaying a list of outsourcings.")
    partner_id = fields.Many2one('res.partner', string='Customer', auto_join=True, tracking=True, domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related="company_id.currency_id", string="Currency", readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", copy=False, ondelete='set null',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", check_company=True,
        help="Analytic account to which this outsourcing is linked for financial management. "
             "Use an analytic account to record cost and revenue on your outsourcing.")

    favorite_user_ids = fields.Many2many(
        'res.users', 'outsourcing_favorite_user_rel', 'outsourcing_id', 'user_id',
        default=_get_default_favorite_user_ids,
        string='Members')
    is_favorite = fields.Boolean(compute='_compute_is_favorite', inverse='_inverse_is_favorite', string='Show outsourcing on dashboard',
        help="Whether this outsourcing should be displayed on your dashboard.")
    label_tasks = fields.Char(string='Use Tasks as', default='Tasks', help="Label used for the tasks of the outsourcing.", translate=True)
    tasks = fields.One2many('outsourcing.task', 'outsourcing_id', string="Task Activities")
    resource_calendar_id = fields.Many2one(
        'resource.calendar', string='Working Time',
        default=lambda self: self.env.company.resource_calendar_id.id,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Timetable working hours to adjust the gantt diagram report")
    type_ids = fields.Many2many('outsourcing.task.type', 'outsourcing_task_type_rel', 'outsourcing_id', 'type_id', string='Tasks Stages')
    task_count = fields.Integer(compute='_compute_task_count', string="Task Count")
    task_ids = fields.One2many('outsourcing.task', 'outsourcing_id', string='Tasks',
                               domain=['|', ('stage_id.fold', '=', False), ('stage_id', '=', False)])
    color = fields.Integer(string='Color Index')
    user_id = fields.Many2one('res.users', string='outsourcing Manager', default=lambda self: self.env.user, tracking=True)
    alias_id = fields.Many2one('mail.alias', string='Alias', ondelete="restrict", required=True,
        help="Internal email associated with this outsourcing. Incoming emails are automatically synchronized "
             "with Tasks (or optionally Issues if the Issue Tracker module is installed).")
    privacy_visibility = fields.Selection([
            ('followers', 'Invited employees'),
            ('employees', 'All employees'),
            ('portal', 'Portal users and all employees'),
        ],
        string='Visibility', required=True,
        default='portal',
        help="Defines the visibility of the tasks of the outsourcing:\n"
                "- Invited employees: employees may only see the followed outsourcing and tasks.\n"
                "- All employees: employees may see all outsourcing and tasks.\n"
                "- Portal users and all employees: employees may see everything."
                "   Portal users may see outsourcing and tasks followed by.\n"
                "   them or by someone of their company.")
    doc_count = fields.Integer(compute='_compute_attached_docs_count', string="Number of documents attached")
    date_start = fields.Date(string='Start Date')
    date = fields.Date(string='Expiration Date', index=True, tracking=True)
    subtask_outsourcing_id = fields.Many2one('outsourcing.outsourcing', string='Sub-task outsourcing', ondelete="restrict",
        help="outsourcing in which sub-tasks of the current outsourcing will be created. It can be the current outsourcing itself.")

    # rating fields
    rating_request_deadline = fields.Datetime(compute='_compute_rating_request_deadline', store=True)
    rating_status = fields.Selection([('stage', 'Rating when changing stage'), ('periodic', 'Periodical Rating'), ('no','No rating')], 'Customer(s) Ratings', help="How to get customer feedback?\n"
                    "- Rating when changing stage: an email will be sent when a task is pulled in another stage.\n"
                    "- Periodical Rating: email will be sent periodically.\n\n"
                    "Don't forget to set up the mail templates on the stages for which you want to get the customer's feedbacks.", default="no", required=True)
    rating_status_period = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('bimonthly', 'Twice a Month'),
        ('monthly', 'Once a Month'), ('quarterly', 'Quarterly'), ('yearly', 'Yearly')
    ], 'Rating Frequency')

    portal_show_rating = fields.Boolean('Rating visible publicly', copy=False)

    _sql_constraints = [
        ('outsourcing_date_greater', 'check(date >= date_start)', 'Error! outsourcing start-date must be lower than outsourcing end-date.')
    ]

    def _compute_access_url(self):
        super(outsourcing, self)._compute_access_url()
        for outsourcing in self:
            outsourcing.access_url = '/my/outsourcing/%s' % outsourcing.id

    def _compute_access_warning(self):
        super(outsourcing, self)._compute_access_warning()
        for outsourcing in self.filtered(lambda x: x.privacy_visibility != 'portal'):
            outsourcing.access_warning = _(
                "The outsourcing cannot be shared with the recipient(s) because the privacy of the outsourcing is too restricted. Set the privacy to 'Visible by following customers' in order to make it accessible by the recipient(s).")

    @api.depends('rating_status', 'rating_status_period')
    def _compute_rating_request_deadline(self):
        periods = {'daily': 1, 'weekly': 7, 'bimonthly': 15, 'monthly': 30, 'quarterly': 90, 'yearly': 365}
        for outsourcing in self:
            outsourcing.rating_request_deadline = fields.datetime.now() + timedelta(days=periods.get(outsourcing.rating_status_period, 0))

    @api.model
    def _map_tasks_default_valeus(self, task, outsourcing):
        """ get the default value for the copied task on outsourcing duplication """
        return {
            'stage_id': task.stage_id.id,
            'name': task.name,
            'company_id': outsourcing.company_id.id,
        }

    def map_tasks(self, new_outsourcing_id):
        """ copy and map tasks from old to new outsourcing """
        outsourcing = self.browse(new_outsourcing_id)
        tasks = self.env['outsourcing.task']
        # We want to copy archived task, but do not propagate an active_test context key
        task_ids = self.env['outsourcing.task'].with_context(active_test=False).search([('outsourcing_id', '=', self.id)], order='parent_id').ids
        old_to_new_tasks = {}
        for task in self.env['outsourcing.task'].browse(task_ids):
            # preserve task name and stage, normally altered during copy
            defaults = self._map_tasks_default_valeus(task, outsourcing)
            if task.parent_id:
                # set the parent to the duplicated task
                defaults['parent_id'] = old_to_new_tasks.get(task.parent_id.id, False)
            new_task = task.copy(defaults)
            old_to_new_tasks[task.id] = new_task.id
            tasks += new_task

        return outsourcing.write({'tasks': [(6, 0, tasks.ids)]})

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        if default is None:
            default = {}
        if not default.get('name'):
            default['name'] = _("%s (copy)") % (self.name)
        outsourcing = super(outsourcing, self).copy(default)
        if self.subtask_outsourcing_id == self:
            outsourcing.subtask_outsourcing_id = outsourcing
        for follower in self.message_follower_ids:
            outsourcing.message_subscribe(partner_ids=follower.partner_id.ids, subtype_ids=follower.subtype_ids.ids)
        if 'tasks' not in default:
            self.map_tasks(outsourcing.id)
        return outsourcing

    # @api.model
    # def create(self, vals):
    #     # Prevent double outsourcing creation
    #     self = self.with_context(mail_create_nosubscribe=True)
    #     outsourcings = super(outsourcing, self).create(vals)
    #     if not vals.get('subtask_outsourcing_id'):
    #         outsourcings.subtask_outsourcing_id = outsourcings.id
    #     if outsourcings.privacy_visibility == 'portal' and outsourcings.partner_id:
    #         outsourcings.message_subscribe(outsourcings.partner_id.ids)
    #     return outsourcings

    def write(self, vals):
        # directly compute is_favorite to dodge allow write access right
        if 'is_favorite' in vals:
            vals.pop('is_favorite')
            self._fields['is_favorite'].determine_inverse(self)
        res = super(outsourcing, self).write(vals) if vals else True
        if 'active' in vals:
            # archiving/unarchiving a outsourcing does it on its tasks, too
            self.with_context(active_test=False).mapped('tasks').write({'active': vals['active']})
        if vals.get('partner_id') or vals.get('privacy_visibility'):
            for outsourcing in self.filtered(lambda outsourcing: outsourcing.privacy_visibility == 'portal'):
                outsourcing.message_subscribe(outsourcing.partner_id.ids)
        return res

    def unlink(self):
        # Check outsourcing is empty
        for outsourcing in self.with_context(active_test=False):
            if outsourcing.tasks:
                raise UserError(_('You cannot delete a outsourcing containing tasks. You can either archive it or first delete all of its tasks.'))
        # Delete the empty related analytic account
        analytic_accounts_to_delete = self.env['account.analytic.account']
        for outsourcing in self:
            if outsourcing.analytic_account_id and not outsourcing.analytic_account_id.line_ids:
                analytic_accounts_to_delete |= outsourcing.analytic_account_id
        result = super(outsourcing, self).unlink()
        analytic_accounts_to_delete.unlink()
        return result

    def message_subscribe(self, partner_ids=None, channel_ids=None, subtype_ids=None):
        """ Subscribe to all existing active tasks when subscribing to a outsourcing """
        res = super(outsourcing, self).message_subscribe(partner_ids=partner_ids, channel_ids=channel_ids, subtype_ids=subtype_ids)
        outsourcing_subtypes = self.env['mail.message.subtype'].browse(subtype_ids) if subtype_ids else None
        task_subtypes = (outsourcing_subtypes.mapped('parent_id') | outsourcing_subtypes.filtered(lambda sub: sub.internal or sub.default)).ids if outsourcing_subtypes else None
        if not subtype_ids or task_subtypes:
            self.mapped('tasks').message_subscribe(
                partner_ids=partner_ids, channel_ids=channel_ids, subtype_ids=task_subtypes)
        return res

    def message_unsubscribe(self, partner_ids=None, channel_ids=None):
        """ Unsubscribe from all tasks when unsubscribing from a outsourcing """
        self.mapped('tasks').message_unsubscribe(partner_ids=partner_ids, channel_ids=channel_ids)
        return super(outsourcing, self).message_unsubscribe(partner_ids=partner_ids, channel_ids=channel_ids)

    # ---------------------------------------------------
    #  Actions
    # ---------------------------------------------------

    def toggle_favorite(self):
        favorite_outsourcings = not_fav_outsourcings = self.env['outsourcing.outsourcing'].sudo()
        for outsourcing in self:
            if self.env.user in outsourcing.favorite_user_ids:
                favorite_outsourcings |= outsourcing
            else:
                not_fav_outsourcings |= outsourcing

        # outsourcing User has no write access for outsourcing.
        not_fav_outsourcings.write({'favorite_user_ids': [(4, self.env.uid)]})
        favorite_outsourcings.write({'favorite_user_ids': [(3, self.env.uid)]})

    def open_tasks(self):
        ctx = dict(self._context)
        ctx.update({'search_default_outsourcing_id': self.id})
        action = self.env['ir.actions.act_window'].for_xml_id('outsourcing', 'act_outsourcing_outsourcing_2_outsourcing_task_all')
        return dict(action, context=ctx)

    def action_view_account_analytic_line(self):
        """ return the action to see all the analytic lines of the outsourcing's analytic account """
        action = self.env.ref('analytic.account_analytic_line_action').read()[0]
        action['context'] = {'default_account_id': self.analytic_account_id.id}
        action['domain'] = [('account_id', '=', self.analytic_account_id.id)]
        return action

    def action_view_all_rating(self):
        """ return the action to see all the rating of the outsourcing, and activate default filters """
        if self.portal_show_rating:
            return {
                'type': 'ir.actions.act_url',
                'name': "Redirect to the Website Projcet Rating Page",
                'target': 'self',
                'url': "/outsourcing/rating/%s" % (self.id,)
            }
        action = self.env['ir.actions.act_window'].for_xml_id('outsourcing', 'rating_rating_action_view_outsourcing_rating')
        action['name'] = _('Ratings of %s') % (self.name,)
        action_context = safe_eval(action['context']) if action['context'] else {}
        action_context.update(self._context)
        action_context['search_default_parent_res_name'] = self.name
        action_context.pop('group_by', None)
        return dict(action, context=action_context)

    # ---------------------------------------------------
    #  Business Methods
    # ---------------------------------------------------

    @api.model
    def _create_analytic_account_from_values(self, values):
        analytic_account = self.env['account.analytic.account'].create({
            'name': values.get('name', _('Unknown Analytic Account')),
            'company_id': values.get('company_id') or self.env.company.id,
            'partner_id': values.get('partner_id'),
            'active': True,
        })
        return analytic_account

    def _create_analytic_account(self):
        for outsourcing in self:
            analytic_account = self.env['account.analytic.account'].create({
                'name': outsourcing.name,
                'company_id': outsourcing.company_id.id,
                'partner_id': outsourcing.partner_id.id,
                'active': True,
            })
            outsourcing.write({'analytic_account_id': analytic_account.id})

    # ---------------------------------------------------
    # Rating business
    # ---------------------------------------------------

    # This method should be called once a day by the scheduler
    @api.model
    def _send_rating_all(self):
        outsourcings = self.search([('rating_status', '=', 'periodic'), ('rating_request_deadline', '<=', fields.Datetime.now())])
        for outsourcing in outsourcings:
            outsourcing.task_ids._send_task_rating_mail()
            outsourcing._compute_rating_request_deadline()
            self.env.cr.commit()


class Task(models.Model):
    _name = "outsourcing.task"
    _description = "Task"
    _date_name = "date_assign"
    _inherit = ['portal.mixin', 'mail.thread.cc', 'mail.activity.mixin', 'rating.mixin']
    _mail_post_access = 'read'
    _order = "priority desc, sequence, id desc"
    _check_company_auto = True

    @api.model
    def default_get(self, fields_list):
        result = super(Task, self).default_get(fields_list)
        # find default value from parent for the not given ones
        parent_task_id = result.get('parent_id') or self._context.get('default_parent_id')
        if parent_task_id:
            parent_values = self._subtask_values_from_parent(parent_task_id)
            for fname, value in parent_values.items():
                if fname not in result:
                    result[fname] = value
        return result

    @api.model
    def _get_default_partner(self):
        if 'default_outsourcing_id' in self.env.context:
            default_outsourcing_id = self.env['outsourcing.outsourcing'].browse(self.env.context['default_outsourcing_id'])
            return default_outsourcing_id.exists().partner_id

    def _get_default_stage_id(self):
        """ Gives default stage_id """
        outsourcing_id = self.env.context.get('default_outsourcing_id')
        if not outsourcing_id:
            return False
        return self.stage_find(outsourcing_id, [('fold', '=', False)])

    @api.model
    def _default_company_id(self):
        if self._context.get('default_outsourcing_id'):
            return self.env['outsourcing.outsourcing'].browse(self._context['default_outsourcing_id']).company_id
        return self.env.company

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        search_domain = [('id', 'in', stages.ids)]
        if 'default_outsourcing_id' in self.env.context:
            search_domain = ['|', ('outsourcing_ids', '=', self.env.context['default_outsourcing_id'])] + search_domain

        stage_ids = stages._search(search_domain, order=order, access_rights_uid=SUPERUSER_ID)
        return stages.browse(stage_ids)

    active = fields.Boolean(default=True)
    name = fields.Char(string='Title', tracking=True, required=True, index=True)
    description = fields.Html(string='Description')
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Important'),
    ], default='0', index=True, string="Priority")
    sequence = fields.Integer(string='Sequence', index=True, default=10,
        help="Gives the sequence order when displaying a list of tasks.")
    stage_id = fields.Many2one('outsourcing.task.type', string='Stage', ondelete='restrict', tracking=True, index=True,
        default=_get_default_stage_id, group_expand='_read_group_stage_ids',
        domain="[('outsourcing_ids', '=', outsourcing_id)]", copy=False)
    tag_ids = fields.Many2many('outsourcing.tags', string='Tags')
    kanban_state = fields.Selection([
        ('normal', 'Grey'),
        ('done', 'Green'),
        ('blocked', 'Red')], string='Kanban State',
        copy=False, default='normal', required=True)
    kanban_state_label = fields.Char(compute='_compute_kanban_state_label', string='Kanban State Label', tracking=True)
    create_date = fields.Datetime("Created On", readonly=True, index=True)
    write_date = fields.Datetime("Last Updated On", readonly=True, index=True)
    date_end = fields.Datetime(string='Ending Date', index=True, copy=False)
    date_assign = fields.Datetime(string='Assigning Date', index=True, copy=False, readonly=True)
    date_deadline = fields.Date(string='Deadline', index=True, copy=False, tracking=True)
    date_deadline_formatted = fields.Char(compute='_compute_date_deadline_formatted')
    date_last_stage_update = fields.Datetime(string='Last Stage Update',
        index=True,
        copy=False,
        readonly=True)
    outsourcing_id = fields.Many2one('outsourcing.outsourcing', string='outsourcing', default=lambda self: self.env.context.get('default_outsourcing_id'),
        index=True, tracking=True, check_company=True, change_default=True)
    planned_hours = fields.Float("Planned Hours", help='It is the time planned to achieve the task. If this document has sub-tasks, it means the time needed to achieve this tasks and its childs.',tracking=True)
    subtask_planned_hours = fields.Float("Subtasks", compute='_compute_subtask_planned_hours', help="Computed using sum of hours planned of all subtasks created from main task. Usually these hours are less or equal to the Planned Hours (of main task).")
    user_id = fields.Many2one('res.users',
        string='Assigned to',
        default=lambda self: self.env.uid,
        index=True, tracking=True)
    partner_id = fields.Many2one('res.partner',
        string='Customer',
        default=lambda self: self._get_default_partner(),
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    partner_city = fields.Char(related='partner_id.city', readonly=False)
    manager_id = fields.Many2one('res.users', string='outsourcing Manager', related='outsourcing_id.user_id', readonly=True, related_sudo=False)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=_default_company_id)
    color = fields.Integer(string='Color Index')
    user_email = fields.Char(related='user_id.email', string='User Email', readonly=True, related_sudo=False)
    attachment_ids = fields.One2many('ir.attachment', compute='_compute_attachment_ids', string="Main Attachments",
        help="Attachment that don't come from message.")
    # In the domain of displayed_image_id, we couln't use attachment_ids because a one2many is represented as a list of commands so we used res_model & res_id
    displayed_image_id = fields.Many2one('ir.attachment', domain="[('res_model', '=', 'outsourcing.task'), ('res_id', '=', id), ('mimetype', 'ilike', 'image')]", string='Cover Image')
    legend_blocked = fields.Char(related='stage_id.legend_blocked', string='Kanban Blocked Explanation', readonly=True, related_sudo=False)
    legend_done = fields.Char(related='stage_id.legend_done', string='Kanban Valid Explanation', readonly=True, related_sudo=False)
    legend_normal = fields.Char(related='stage_id.legend_normal', string='Kanban Ongoing Explanation', readonly=True, related_sudo=False)
    parent_id = fields.Many2one('outsourcing.task', string='Parent Task', index=True)
    child_ids = fields.One2many('outsourcing.task', 'parent_id', string="Sub-tasks", context={'active_test': False})
    subtask_outsourcing_id = fields.Many2one('outsourcing.outsourcing', related="outsourcing_id.subtask_outsourcing_id", string='Sub-task outsourcing', readonly=True)
    subtask_count = fields.Integer("Sub-task count", compute='_compute_subtask_count')
    email_from = fields.Char(string='Email', help="These people will receive email.", index=True)
    # Computed field about working time elapsed between record creation and assignation/closing.
    working_hours_open = fields.Float(compute='_compute_elapsed', string='Working hours to assign', store=True, group_operator="avg")
    working_hours_close = fields.Float(compute='_compute_elapsed', string='Working hours to close', store=True, group_operator="avg")
    working_days_open = fields.Float(compute='_compute_elapsed', string='Working days to assign', store=True, group_operator="avg")
    working_days_close = fields.Float(compute='_compute_elapsed', string='Working days to close', store=True, group_operator="avg")
    # customer portal: include comment and incoming emails in communication history
    website_message_ids = fields.One2many(domain=lambda self: [('model', '=', self._name), ('message_type', 'in', ['email', 'comment'])])

    @api.depends('date_deadline')
    def _compute_date_deadline_formatted(self):
        for task in self:
            task.date_deadline_formatted = format_date(self.env, task.date_deadline) if task.date_deadline else None

    def _compute_attachment_ids(self):
        for task in self:
            attachment_ids = self.env['ir.attachment'].search([('res_id', '=', task.id), ('res_model', '=', 'outsourcing.task')]).ids
            message_attachment_ids = task.mapped('message_ids.attachment_ids').ids  # from mail_thread
            task.attachment_ids = [(6, 0, list(set(attachment_ids) - set(message_attachment_ids)))]

    @api.depends('create_date', 'date_end', 'date_assign')
    def _compute_elapsed(self):
        task_linked_to_calendar = self.filtered(
            lambda task: task.outsourcing_id.resource_calendar_id and task.create_date
        )
        for task in task_linked_to_calendar:
            dt_create_date = fields.Datetime.from_string(task.create_date)

            if task.date_assign:
                dt_date_assign = fields.Datetime.from_string(task.date_assign)
                duration_data = task.outsourcing_id.resource_calendar_id.get_work_duration_data(dt_create_date, dt_date_assign, compute_leaves=True)
                task.working_hours_open = duration_data['hours']
                task.working_days_open = duration_data['days']
            else:
                task.working_hours_open = 0.0
                task.working_days_open = 0.0

            if task.date_end:
                dt_date_end = fields.Datetime.from_string(task.date_end)
                duration_data = task.outsourcing_id.resource_calendar_id.get_work_duration_data(dt_create_date, dt_date_end, compute_leaves=True)
                task.working_hours_close = duration_data['hours']
                task.working_days_close = duration_data['days']
            else:
                task.working_hours_close = 0.0
                task.working_days_close = 0.0

        (self - task_linked_to_calendar).update(dict.fromkeys(
            ['working_hours_open', 'working_hours_close', 'working_days_open', 'working_days_close'], 0.0))

    @api.depends('stage_id', 'kanban_state')
    def _compute_kanban_state_label(self):
        for task in self:
            if task.kanban_state == 'normal':
                task.kanban_state_label = task.legend_normal
            elif task.kanban_state == 'blocked':
                task.kanban_state_label = task.legend_blocked
            else:
                task.kanban_state_label = task.legend_done

    def _compute_access_url(self):
        super(Task, self)._compute_access_url()
        for task in self:
            task.access_url = '/my/task/%s' % task.id

    def _compute_access_warning(self):
        super(Task, self)._compute_access_warning()
        for task in self.filtered(lambda x: x.outsourcing_id.privacy_visibility != 'portal'):
            task.access_warning = _(
                "The task cannot be shared with the recipient(s) because the privacy of the outsourcing is too restricted. Set the privacy of the outsourcing to 'Visible by following customers' in order to make it accessible by the recipient(s).")

    @api.depends('child_ids.planned_hours')
    def _compute_subtask_planned_hours(self):
        for task in self:
            task.subtask_planned_hours = sum(task.child_ids.mapped('planned_hours'))

    @api.depends('child_ids')
    def _compute_subtask_count(self):
        """ Note: since we accept only one level subtask, we can use a read_group here """
        task_data = self.env['outsourcing.task'].read_group([('parent_id', 'in', self.ids)], ['parent_id'], ['parent_id'])
        mapping = dict((data['parent_id'][0], data['parent_id_count']) for data in task_data)
        for task in self:
            task.subtask_count = mapping.get(task.id, 0)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        self.email_from = self.partner_id.email

    @api.onchange('parent_id')
    def _onchange_parent_id(self):
        if self.parent_id:
            for field_name, value in self._subtask_values_from_parent(self.parent_id.id).items():
                if not self[field_name]:
                    self[field_name] = value

    @api.onchange('outsourcing_id')
    def _onchange_outsourcing(self):
        if self.outsourcing_id:
            # find partner
            if self.outsourcing_id.partner_id:
                self.partner_id = self.outsourcing_id.partner_id
            # find stage
            if self.outsourcing_id not in self.stage_id.outsourcing_ids:
                self.stage_id = self.stage_find(self.outsourcing_id.id, [('fold', '=', False)])
            # keep multi company consistency
            self.company_id = self.outsourcing_id.company_id
        else:
            self.stage_id = False
    
    @api.onchange('company_id')
    def _onchange_task_company(self):
        if self.outsourcing_id.company_id != self.company_id:
            self.outsourcing_id = False

    @api.constrains('parent_id', 'child_ids')
    def _check_subtask_level(self):
        for task in self:
            if task.parent_id and task.child_ids:
                raise ValidationError(_('Task %s cannot have several subtask levels.' % (task.name,)))

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        if default is None:
            default = {}
        if not default.get('name'):
            default['name'] = _("%s (copy)") % self.name
        return super(Task, self).copy(default)

    @api.constrains('parent_id')
    def _check_parent_id(self):
        for task in self:
            if not task._check_recursion():
                raise ValidationError(_('Error! You cannot create recursive hierarchy of task(s).'))

    @api.model
    def get_empty_list_help(self, help):
        tname = _("task")
        outsourcing_id = self.env.context.get('default_outsourcing_id', False)
        if outsourcing_id:
            name = self.env['outsourcing.outsourcing'].browse(outsourcing_id).label_tasks
            if name: tname = name.lower()

        self = self.with_context(
            empty_list_help_id=self.env.context.get('default_outsourcing_id'),
            empty_list_help_model='outsourcing.outsourcing',
            empty_list_help_document_name=tname,
        )
        return super(Task, self).get_empty_list_help(help)

    # ----------------------------------------
    # Case management
    # ----------------------------------------

    def stage_find(self, section_id, domain=[], order='sequence'):
        """ Override of the base.stage method
            Parameter of the stage search taken from the lead:
            - section_id: if set, stages must belong to this section or
              be a default stage; if not set, stages must be default
              stages
        """
        # collect all section_ids
        section_ids = []
        if section_id:
            section_ids.append(section_id)
        section_ids.extend(self.mapped('outsourcing_id').ids)
        search_domain = []
        if section_ids:
            search_domain = [('|')] * (len(section_ids) - 1)
            for section_id in section_ids:
                search_domain.append(('outsourcing_ids', '=', section_id))
        search_domain += list(domain)
        # perform search, return the first found
        return self.env['outsourcing.task.type'].search(search_domain, order=order, limit=1).id

    # ------------------------------------------------
    # CRUD overrides
    # ------------------------------------------------

    @api.model
    def create(self, vals):
        # context: no_log, because subtype already handle this
        context = dict(self.env.context)
        # for default stage
        if vals.get('outsourcing_id') and not context.get('default_outsourcing_id'):
            context['default_outsourcing_id'] = vals.get('outsourcing_id')
        # user_id change: update date_assign
        if vals.get('user_id'):
            vals['date_assign'] = fields.Datetime.now()
        # Stage change: Update date_end if folded stage and date_last_stage_update
        if vals.get('stage_id'):
            vals.update(self.update_date_end(vals['stage_id']))
            vals['date_last_stage_update'] = fields.Datetime.now()
        # substask default values
        if vals.get('parent_id'):
            for fname, value in self._subtask_values_from_parent(vals['parent_id']).items():
                if fname not in vals:
                    vals[fname] = value
        task = super(Task, self.with_context(context)).create(vals)
        if task.outsourcing_id.privacy_visibility == 'portal':
            task._portal_ensure_token()
        return task

    def write(self, vals):
        now = fields.Datetime.now()
        # stage change: update date_last_stage_update
        if 'stage_id' in vals:
            vals.update(self.update_date_end(vals['stage_id']))
            vals['date_last_stage_update'] = now
            # reset kanban state when changing stage
            if 'kanban_state' not in vals:
                vals['kanban_state'] = 'normal'
        # user_id change: update date_assign
        if vals.get('user_id') and 'date_assign' not in vals:
            vals['date_assign'] = now

        result = super(Task, self).write(vals)
        # rating on stage
        if 'stage_id' in vals and vals.get('stage_id'):
            self.filtered(lambda x: x.outsourcing_id.rating_status == 'stage')._send_task_rating_mail(force_send=True)
        return result

    def update_date_end(self, stage_id):
        outsourcing_task_type = self.env['outsourcing.task.type'].browse(stage_id)
        if outsourcing_task_type.fold:
            return {'date_end': fields.Datetime.now()}
        return {'date_end': False}

    # ---------------------------------------------------
    # Subtasks
    # ---------------------------------------------------

    def _subtask_default_fields(self):
        """ Return the list of field name for default value when creating a subtask """
        return ['partner_id', 'email_from']

    def _subtask_values_from_parent(self, parent_id):
        """ Get values for substask implied field of the given"""
        result = {}
        parent_task = self.env['outsourcing.task'].browse(parent_id)
        for field_name in self._subtask_default_fields():
            result[field_name] = parent_task[field_name]
        # special case for the subtask default outsourcing
        result['outsourcing_id'] = parent_task.outsourcing_id.subtask_outsourcing_id
        return self._convert_to_write(result)

    # ---------------------------------------------------
    # Mail gateway
    # ---------------------------------------------------

    def _track_template(self, changes):
        res = super(Task, self)._track_template(changes)
        test_task = self[0]
        if 'stage_id' in changes and test_task.stage_id.mail_template_id:
            res['stage_id'] = (test_task.stage_id.mail_template_id, {
                'auto_delete_message': True,
                'subtype_id': self.env['ir.model.data'].xmlid_to_res_id('mail.mt_note'),
                'email_layout_xmlid': 'mail.mail_notification_light'
            })
        return res

    def _creation_subtype(self):
        return self.env.ref('outsourcing.mt_task_new')

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'kanban_state_label' in init_values and self.kanban_state == 'blocked':
            return self.env.ref('outsourcing.mt_task_blocked')
        elif 'kanban_state_label' in init_values and self.kanban_state == 'done':
            return self.env.ref('outsourcing.mt_task_ready')
        elif 'stage_id' in init_values:
            return self.env.ref('outsourcing.mt_task_stage')
        return super(Task, self)._track_subtype(init_values)

    def _notify_get_groups(self, msg_vals=None):
        """ Handle outsourcing users and managers recipients that can assign
        tasks and create new one directly from notification emails. Also give
        access button to portal users and portal customers. If they are notified
        they should probably have access to the document. """
        groups = super(Task, self)._notify_get_groups(msg_vals=msg_vals)
        msg_vals = msg_vals or {}
        self.ensure_one()

        outsourcing_user_group_id = self.env.ref('outsourcing.group_outsourcing_user').id
        new_group = (
            'group_outsourcing_user',
            lambda pdata: pdata['type'] == 'user' and outsourcing_user_group_id in pdata['groups'],
            {},
        )

        if not self.user_id and not self.stage_id.fold:
            take_action = self._notify_get_action_link('assign', **msg_vals)
            outsourcing_actions = [{'url': take_action, 'title': _('I take it')}]
            new_group[2]['actions'] = outsourcing_actions

        groups = [new_group] + groups

        for group_name, group_method, group_data in groups:
            if group_name != 'customer':
                group_data['has_button_access'] = True

        return groups

    def _notify_get_reply_to(self, default=None, records=None, company=None, doc_names=None):
        """ Override to set alias of tasks to their outsourcing if any. """
        aliases = self.sudo().mapped('outsourcing_id')._notify_get_reply_to(default=default, records=None, company=company, doc_names=None)
        res = {task.id: aliases.get(task.outsourcing_id.id) for task in self}
        leftover = self.filtered(lambda rec: not rec.outsourcing_id)
        if leftover:
            res.update(super(Task, leftover)._notify_get_reply_to(default=default, records=None, company=company, doc_names=doc_names))
        return res

    def email_split(self, msg):
        email_list = tools.email_split((msg.get('to') or '') + ',' + (msg.get('cc') or ''))
        # check left-part is not already an alias
        aliases = self.mapped('outsourcing_id.alias_name')
        return [x for x in email_list if x.split('@')[0] not in aliases]

    @api.model
    def message_new(self, msg, custom_values=None):
        """ Overrides mail_thread message_new that is called by the mailgateway
            through message_process.
            This override updates the document according to the email.
        """
        # remove default author when going through the mail gateway. Indeed we
        # do not want to explicitly set user_id to False; however we do not
        # want the gateway user to be responsible if no other responsible is
        # found.
        create_context = dict(self.env.context or {})
        create_context['default_user_id'] = False
        if custom_values is None:
            custom_values = {}
        defaults = {
            'name': msg.get('subject') or _("No Subject"),
            'email_from': msg.get('from'),
            'planned_hours': 0.0,
            'partner_id': msg.get('author_id')
        }
        defaults.update(custom_values)

        task = super(Task, self.with_context(create_context)).message_new(msg, custom_values=defaults)
        email_list = task.email_split(msg)
        partner_ids = [p.id for p in self.env['mail.thread']._mail_find_partner_from_emails(email_list, records=task, force_create=False) if p]
        task.message_subscribe(partner_ids)
        return task

    def message_update(self, msg, update_vals=None):
        """ Override to update the task according to the email. """
        email_list = self.email_split(msg)
        partner_ids = [p.id for p in self.env['mail.thread']._mail_find_partner_from_emails(email_list, records=self, force_create=False) if p]
        self.message_subscribe(partner_ids)
        return super(Task, self).message_update(msg, update_vals=update_vals)

    def _message_get_suggested_recipients(self):
        recipients = super(Task, self)._message_get_suggested_recipients()
        for task in self:
            if task.partner_id:
                reason = _('Customer Email') if task.partner_id.email else _('Customer')
                task._message_add_suggested_recipient(recipients, partner=task.partner_id, reason=reason)
            elif task.email_from:
                task._message_add_suggested_recipient(recipients, email=task.email_from, reason=_('Customer Email'))
        return recipients

    def _notify_email_header_dict(self):
        headers = super(Task, self)._notify_email_header_dict()
        if self.outsourcing_id:
            current_objects = [h for h in headers.get('X-Odoo-Objects', '').split(',') if h]
            current_objects.insert(0, 'outsourcing.outsourcing-%s, ' % self.outsourcing_id.id)
            headers['X-Odoo-Objects'] = ','.join(current_objects)
        if self.tag_ids:
            headers['X-Odoo-Tags'] = ','.join(self.tag_ids.mapped('name'))
        return headers

    def _message_post_after_hook(self, message, msg_vals):
        if self.email_from and not self.partner_id:
            # we consider that posting a message with a specified recipient (not a follower, a specific one)
            # on a document without customer means that it was created through the chatter using
            # suggested recipients. This heuristic allows to avoid ugly hacks in JS.
            new_partner = message.partner_ids.filtered(lambda partner: partner.email == self.email_from)
            if new_partner:
                self.search([
                    ('partner_id', '=', False),
                    ('email_from', '=', new_partner.email),
                    ('stage_id.fold', '=', False)]).write({'partner_id': new_partner.id})
        return super(Task, self)._message_post_after_hook(message, msg_vals)

    def action_assign_to_me(self):
        self.write({'user_id': self.env.user.id})

    def action_open_parent_task(self):
        return {
            'name': _('Parent Task'),
            'view_mode': 'form',
            'res_model': 'outsourcing.task',
            'res_id': self.parent_id.id,
            'type': 'ir.actions.act_window',
            'context': dict(self._context, create=False)
        }

    def action_subtask(self):
        action = self.env.ref('outsourcing.outsourcing_task_action_sub_task').read()[0]

        # only display subtasks of current task
        action['domain'] = [('id', 'child_of', self.id), ('id', '!=', self.id)]

        # update context, with all default values as 'quick_create' does not contains all field in its view
        if self._context.get('default_outsourcing_id'):
            default_outsourcing = self.env['outsourcing.outsourcing'].browse(self.env.context['default_outsourcing_id'])
        else:
            default_outsourcing = self.outsourcing_id.subtask_outsourcing_id or self.outsourcing_id
        ctx = dict(self.env.context)
        ctx.update({
            'default_name': self.env.context.get('name', self.name) + ':',
            'default_parent_id': self.id,  # will give default subtask field in `default_get`
            'default_company_id': default_outsourcing.company_id.id if default_outsourcing else self.env.company.id,
            'search_default_parent_id': self.id,
        })
        parent_values = self._subtask_values_from_parent(self.id)
        for fname, value in parent_values.items():
            if 'default_' + fname not in ctx:
                ctx['default_' + fname] = value
        action['context'] = ctx

        return action

    # ---------------------------------------------------
    # Rating business
    # ---------------------------------------------------

    def _send_task_rating_mail(self, force_send=False):
        for task in self:
            rating_template = task.stage_id.rating_template_id
            if rating_template:
                task.rating_send_request(rating_template, lang=task.partner_id.lang, force_send=force_send)

    def rating_get_partner_id(self):
        res = super(Task, self).rating_get_partner_id()
        if not res and self.outsourcing_id.partner_id:
            return self.outsourcing_id.partner_id
        return res

    def rating_apply(self, rate, token=None, feedback=None, subtype=None):
        return super(Task, self).rating_apply(rate, token=token, feedback=feedback, subtype="outsourcing.mt_task_rating")

    def _rating_get_parent_field_name(self):
        return 'outsourcing_id'


class outsourcingTags(models.Model):
    """ Tags of outsourcing's tasks """
    _name = "outsourcing.tags"
    _description = "outsourcing Tags"

    name = fields.Char('Tag Name', required=True)
    color = fields.Integer(string='Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists!"),
    ]

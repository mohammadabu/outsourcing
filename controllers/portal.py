# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import OrderedDict
from operator import itemgetter

from odoo import http, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.tools import groupby as groupbyelem

from odoo.osv.expression import OR


class CustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self):
        values = super(CustomerPortal, self)._prepare_home_portal_values()
        values['outsourcing_count'] = request.env['outsourcing.outsourcing'].search_count([])
        values['task_count'] = request.env['outsourcing.task'].search_count([])
        return values

    # ------------------------------------------------------------
    # My outsourcing
    # ------------------------------------------------------------
    def _outsourcing_get_page_view_values(self, outsourcing, access_token, **kwargs):
        values = {
            'page_name': 'outsourcing',
            'outsourcing': outsourcing,
        }
        return self._get_page_view_values(outsourcing, access_token, values, 'my_outsourcings_history', False, **kwargs)

    @http.route(['/my/outsourcings', '/my/outsourcings/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_outsourcings(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        outsourcing = request.env['outsourcing.outsourcing']
        domain = []

        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'create_date desc'},
            'name': {'label': _('Name'), 'order': 'name'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # archive groups - Default Group By 'create_date'
        archive_groups = self._get_archive_groups('outsourcing.outsourcing', domain) if values.get('my_details') else []
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]
        # outsourcings count
        outsourcing_count = outsourcing.search_count(domain)
        # pager
        pager = portal_pager(
            url="/my/outsourcings",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=outsourcing_count,
            page=page,
            step=self._items_per_page
        )

        # content according to pager and archive selected
        outsourcings = outsourcing.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_outsourcings_history'] = outsourcings.ids[:100]

        values.update({
            'date': date_begin,
            'date_end': date_end,
            'outsourcings': outsourcings,
            'page_name': 'outsourcing',
            'archive_groups': archive_groups,
            'default_url': '/my/outsourcings',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby
        })
        return request.render("outsourcing.portal_my_outsourcings", values)

    @http.route(['/my/outsourcing/<int:outsourcing_id>'], type='http', auth="public", website=True)
    def portal_my_outsourcing(self, outsourcing_id=None, access_token=None, **kw):
        try:
            outsourcing_sudo = self._document_check_access('outsourcing.outsourcing', outsourcing_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        values = self._outsourcing_get_page_view_values(outsourcing_sudo, access_token, **kw)
        return request.render("outsourcing.portal_my_outsourcing", values)

    # ------------------------------------------------------------
    # My Task
    # ------------------------------------------------------------
    def _task_get_page_view_values(self, task, access_token, **kwargs):
        values = {
            'page_name': 'task',
            'task': task,
            'user': request.env.user
        }
        return self._get_page_view_values(task, access_token, values, 'my_tasks_history', False, **kwargs)

    @http.route(['/my/tasks', '/my/tasks/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_tasks(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, search=None, search_in='content', groupby='outsourcing', **kw):
        values = self._prepare_portal_layout_values()
        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'create_date desc'},
            'name': {'label': _('Title'), 'order': 'name'},
            'stage': {'label': _('Stage'), 'order': 'stage_id'},
            'update': {'label': _('Last Stage Update'), 'order': 'date_last_stage_update desc'},
        }
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
        }
        searchbar_inputs = {
            'content': {'input': 'content', 'label': _('Search <span class="nolabel"> (in Content)</span>')},
            'message': {'input': 'message', 'label': _('Search in Messages')},
            'customer': {'input': 'customer', 'label': _('Search in Customer')},
            'stage': {'input': 'stage', 'label': _('Search in Stages')},
            'all': {'input': 'all', 'label': _('Search in All')},
        }
        searchbar_groupby = {
            'none': {'input': 'none', 'label': _('None')},
            'outsourcing': {'input': 'outsourcing', 'label': _('outsourcing')},
        }

        # extends filterby criteria with outsourcing the customer has access to
        outsourcings = request.env['outsourcing.outsourcing'].search([])
        for outsourcing in outsourcings:
            searchbar_filters.update({
                str(outsourcing.id): {'label': outsourcing.name, 'domain': [('outsourcing_id', '=', outsourcing.id)]}
            })

        # extends filterby criteria with outsourcing (criteria name is the outsourcing id)
        # Note: portal users can't view outsourcings they don't follow
        outsourcing_groups = request.env['outsourcing.task'].read_group([('outsourcing_id', 'not in', outsourcings.ids)],
                                                                ['outsourcing_id'], ['outsourcing_id'])
        for group in outsourcing_groups:
            proj_id = group['outsourcing_id'][0] if group['outsourcing_id'] else False
            proj_name = group['outsourcing_id'][1] if group['outsourcing_id'] else _('Others')
            searchbar_filters.update({
                str(proj_id): {'label': proj_name, 'domain': [('outsourcing_id', '=', proj_id)]}
            })

        # default sort by value
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        # default filter by value
        if not filterby:
            filterby = 'all'
        domain = searchbar_filters.get(filterby, searchbar_filters.get('all'))['domain']

        # archive groups - Default Group By 'create_date'
        archive_groups = self._get_archive_groups('outsourcing.task', domain) if values.get('my_details') else []
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        # search
        if search and search_in:
            search_domain = []
            if search_in in ('content', 'all'):
                search_domain = OR([search_domain, ['|', ('name', 'ilike', search), ('description', 'ilike', search)]])
            if search_in in ('customer', 'all'):
                search_domain = OR([search_domain, [('partner_id', 'ilike', search)]])
            if search_in in ('message', 'all'):
                search_domain = OR([search_domain, [('message_ids.body', 'ilike', search)]])
            if search_in in ('stage', 'all'):
                search_domain = OR([search_domain, [('stage_id', 'ilike', search)]])
            domain += search_domain

        # task count
        task_count = request.env['outsourcing.task'].search_count(domain)
        # pager
        pager = portal_pager(
            url="/my/tasks",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby, 'search_in': search_in, 'search': search},
            total=task_count,
            page=page,
            step=self._items_per_page
        )
        # content according to pager and archive selected
        if groupby == 'outsourcing':
            order = "outsourcing_id, %s" % order  # force sort on outsourcing first to group by outsourcing in view
        tasks = request.env['outsourcing.task'].search(domain, order=order, limit=self._items_per_page, offset=(page - 1) * self._items_per_page)
        request.session['my_tasks_history'] = tasks.ids[:100]
        if groupby == 'outsourcing':
            grouped_tasks = [request.env['outsourcing.task'].concat(*g) for k, g in groupbyelem(tasks, itemgetter('outsourcing_id'))]
        else:
            grouped_tasks = [tasks]

        values.update({
            'date': date_begin,
            'date_end': date_end,
            'grouped_tasks': grouped_tasks,
            'page_name': 'task',
            'archive_groups': archive_groups,
            'default_url': '/my/tasks',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_groupby': searchbar_groupby,
            'searchbar_inputs': searchbar_inputs,
            'search_in': search_in,
            'sortby': sortby,
            'groupby': groupby,
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'filterby': filterby,
        })
        return request.render("outsourcing.portal_my_tasks", values)

    @http.route(['/my/task/<int:task_id>'], type='http', auth="public", website=True)
    def portal_my_task(self, task_id, access_token=None, **kw):
        try:
            task_sudo = self._document_check_access('outsourcing.task', task_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        # ensure attachment are accessible with access token inside template
        for attachment in task_sudo.attachment_ids:
            attachment.generate_access_token()
        values = self._task_get_page_view_values(task_sudo, access_token, **kw)
        return request.render("outsourcing.portal_my_task", values)

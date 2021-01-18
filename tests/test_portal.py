# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.outsourcing.tests.test_access_rights import TestPortaloutsourcingBase
from odoo.exceptions import AccessError
from odoo.tools import mute_logger


class TestPortaloutsourcing(TestPortaloutsourcingBase):
    @mute_logger('odoo.addons.base.models.ir_model')
    def test_portal_outsourcing_access_rights(self):
        pigs = self.outsourcing_pigs
        pigs.write({'privacy_visibility': 'portal'})

        # Do: Alfred reads outsourcing -> ok (employee ok public)
        pigs.with_user(self.user_outsourcinguser).read(['user_id'])
        # Test: all outsourcing tasks visible
        tasks = self.env['outsourcing.task'].with_user(self.user_outsourcinguser).search([('outsourcing_id', '=', pigs.id)])
        self.assertEqual(tasks, self.task_1 | self.task_2 | self.task_3 | self.task_4 | self.task_5 | self.task_6,
                         'access rights: outsourcing user should see all tasks of a portal outsourcing')

        # Do: Bert reads outsourcing -> crash, no group
        self.assertRaises(AccessError, pigs.with_user(self.user_noone).read, ['user_id'])
        # Test: no outsourcing task searchable
        self.assertRaises(AccessError, self.env['outsourcing.task'].with_user(self.user_noone).search, [('outsourcing_id', '=', pigs.id)])

        # Data: task follower
        pigs.with_user(self.user_outsourcingmanager).message_subscribe(partner_ids=[self.user_portal.partner_id.id])
        self.task_1.with_user(self.user_outsourcinguser).message_subscribe(partner_ids=[self.user_portal.partner_id.id])
        self.task_3.with_user(self.user_outsourcinguser).message_subscribe(partner_ids=[self.user_portal.partner_id.id])
        # Do: Chell reads outsourcing -> ok (portal ok public)
        pigs.with_user(self.user_portal).read(['user_id'])
        # Do: Donovan reads outsourcing -> ko (public ko portal)
        self.assertRaises(AccessError, pigs.with_user(self.user_public).read, ['user_id'])
        # Test: no access right to outsourcing.task
        self.assertRaises(AccessError, self.env['outsourcing.task'].with_user(self.user_public).search, [])
        # Data: task follower cleaning
        self.task_1.with_user(self.user_outsourcinguser).message_unsubscribe(partner_ids=[self.user_portal.partner_id.id])
        self.task_3.with_user(self.user_outsourcinguser).message_unsubscribe(partner_ids=[self.user_portal.partner_id.id])

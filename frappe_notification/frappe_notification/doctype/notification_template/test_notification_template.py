# Copyright (c) 2022, Leam Technology Systems and Contributors
# See license.txt

# import frappe
import unittest
from faker import Faker

import frappe
from frappe_testing import TestFixture
from frappe_notification import (
    NotificationClient,
    NotificationClientFixtures,
    NotificationChannelFixtures,
    NotificationClientNotFound,
    set_active_notification_client)

from .notification_template import (
    NotificationTemplate,
    AllowedClientNotManagedByManager,
    OnlyManagerTemplatesCanBeShared)


class NotificationTemplateFixtures(TestFixture):

    def __init__(self):
        super().__init__()
        self.DEFAULT_DOCTYPE = "Notification Template"
        self.dependent_fixtures = [NotificationClientFixtures]

    def make_fixtures(self):
        clients: NotificationClientFixtures = self.get_dependent_fixture_instance(
            "Notification Client")

        managers = [x for x in clients if x.is_client_manager]
        for manager in managers:
            self.make_otp_template(manager, clients)
            self.make_welcome_template(manager, clients)

    def make_otp_template(
            self, manager: NotificationClient, clients: NotificationClientFixtures):

        managed_clients = clients.get_clients_managed_by(manager.name)

        t = NotificationTemplate(dict(
            doctype="Notification Template",
            title="OTP Template",
            subject="This is your OTP: {{ otp }}",
            content="OTP For Life!",
            created_by=manager.name,
            allowed_clients=[
                dict(notification_client=x.name)
                for x in managed_clients
            ]
        ))
        self.add_document(t.insert())

    def make_welcome_template(
            self, manager: NotificationClient,
            clients: NotificationClientFixtures):
        pass


class TestNotificationTemplate(unittest.TestCase):

    channels = NotificationChannelFixtures()
    clients = NotificationClientFixtures()
    templates = NotificationTemplateFixtures()
    faker = Faker()

    @classmethod
    def setUpClass(cls):
        cls.channels.setUp()
        cls.clients.setUp()

    @classmethod
    def tearDownClass(cls):
        cls.clients.tearDown()
        cls.channels.tearDown()

    def setUp(self):
        self.templates.setUp()

    def tearDown(self) -> None:
        set_active_notification_client(None)
        self.templates.tearDown()

    def test_created_by(self):
        client = self.clients.get_non_manager_client()

        # When no active client is available, result should be None
        d = NotificationTemplate(dict(
            doctype="Notification Template",
            title=self.faker.first_name(),))
        with self.assertRaises(NotificationClientNotFound):
            d.insert()

        # Should go smooth
        set_active_notification_client(client.name)
        self.templates.add_document(d.insert())
        self.assertEqual(d.created_by, client.name)

    def test_set_allowed_clients_on_non_manager_template(self):
        """
        Let's try setting Template.allowed_clients[] on a template created by a non-manager
        """
        client = self.clients.get_non_manager_client()
        set_active_notification_client(client.name)

        d = NotificationTemplate(dict(
            doctype="Notification Template",
            title=self.faker.first_name(),
            allowed_clients=[
                dict(notification_client=self.clients.get_non_manager_client().name)
            ]))

        with self.assertRaises(OnlyManagerTemplatesCanBeShared):
            d.insert()

    def test_set_allowed_client_on_non_managed_client(self):
        manager = self.clients.get_manager_client()
        client = None
        while (client is None or client.managed_by == manager.name):
            client = self.clients.get_non_manager_client()

        set_active_notification_client(manager.name)
        d = NotificationTemplate(dict(
            doctype="Notification Template",
            title=self.faker.first_name(),
            allowed_clients=[
                dict(notification_client=client.name)
            ]))

        with self.assertRaises(AllowedClientNotManagedByManager):
            d.insert()

    def test_lang_templates(self):

        PREDEFINED_ROW_COUNT = 1
        d = NotificationTemplate(dict(
            doctype="Notification Template",
            title=self.faker.first_name(),
            lang="en",
            lang_templates=[
                dict(lang="ar", subject="A", content="B")
            ]))

        # Try setting the same 'en' row
        d.append("lang_templates", dict(lang=d.lang, subject=self.faker.first_name()))
        d.validate_language_templates()
        self.assertEqual(len(d.lang_templates), PREDEFINED_ROW_COUNT)

        # Try add empty content & subject
        d.append("lang_templates", dict(lang="en-US", subject=None))
        d.validate_language_templates()
        self.assertEqual(len(d.lang_templates), PREDEFINED_ROW_COUNT)

        # Try adding duplicate lang
        d.append("lang_templates", dict(lang=d.lang_templates[0].lang, subject="A"))
        d.validate_language_templates()
        self.assertEqual(len(d.lang_templates), PREDEFINED_ROW_COUNT)

    def test_get_channel_sender(self):

        _CHANNEL = self.channels[0].name

        d = NotificationTemplate(dict(
            doctype="Notification Template",
            title=self.faker.first_name(),
            lang="en",
            channel_senders=[
                dict(channel=self.channels[-1].name, sender_type="C", sender="D"),
                dict(channel=_CHANNEL, sender_type="A", sender="B"),
            ]))

        sender_type, sender = d.get_channel_sender(_CHANNEL)
        self.assertEqual(sender_type, "A")
        self.assertEqual(sender, "B")

    def test_get_lang_templates(self):
        _lang_templates = frappe._dict({
            "en": ("en-subject!", "en-content!"),
            "ar": ("ar-subject", "ar-content"),
            "es": ("es-subject", "es-content"),
        })

        d = NotificationTemplate(dict(
            doctype="Notification Template",
            title=self.faker.first_name(),
            lang="en",
            subject=_lang_templates["en"][0],
            content=_lang_templates["en"][1],
            lang_templates=[
                dict(lang="ar", subject=_lang_templates["ar"][0], content=_lang_templates["ar"][1]),
                dict(lang="es", subject=_lang_templates["es"][0], content=_lang_templates["es"][1]),
            ]))

        self.assertEqual(d.get_lang_templates("en"), _lang_templates["en"])
        self.assertEqual(d.get_lang_templates("ar"), _lang_templates["ar"])
        self.assertEqual(d.get_lang_templates("es"), _lang_templates["es"])

        # Now, for a lang for which template is not defined
        self.assertEqual(d.get_lang_templates("pr"), _lang_templates["en"])

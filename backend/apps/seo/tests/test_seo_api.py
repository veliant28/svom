from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.seo.models import SeoMetaOverride, SeoMetaTemplate
from apps.users.models import User


class SeoApiTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="seo-admin@test.local",
            first_name="SEO",
            password="demo12345",
            is_staff=True,
            is_superuser=True,
        )
        self.token = Token.objects.create(user=self.staff)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

    def test_backoffice_settings_and_dashboard(self):
        settings_response = self.client.get(reverse("seo_api:backoffice-settings"), **self.auth)
        self.assertEqual(settings_response.status_code, status.HTTP_200_OK)
        self.assertIn("default_meta_title_uk", settings_response.data)

        update_response = self.client.patch(
            reverse("seo_api:backoffice-settings"),
            {
                "is_enabled": True,
                "canonical_base_url": "https://svom.example",
                "default_robots_directive": "index,follow",
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["canonical_base_url"], "https://svom.example")

        dashboard_response = self.client.get(reverse("seo_api:backoffice-dashboard"), **self.auth)
        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertIn("seo_health_by_entity", dashboard_response.data)

    def test_google_settings_validation(self):
        invalid_ga4 = self.client.patch(
            reverse("seo_api:backoffice-google"),
            {"ga4_measurement_id": "bad-ga4"},
            format="json",
            **self.auth,
        )
        self.assertEqual(invalid_ga4.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ga4_measurement_id", invalid_ga4.data)

        invalid_gtm = self.client.patch(
            reverse("seo_api:backoffice-google"),
            {"gtm_container_id": "bad-gtm"},
            format="json",
            **self.auth,
        )
        self.assertEqual(invalid_gtm.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("gtm_container_id", invalid_gtm.data)

    def test_templates_and_overrides_crud(self):
        template_create = self.client.post(
            reverse("seo_api:backoffice-template-list"),
            {
                "entity_type": "product",
                "locale": "uk",
                "title_template": "{name} | {brand}",
                "description_template": "{name}",
                "h1_template": "{name}",
                "og_title_template": "{name}",
                "og_description_template": "{category}",
                "is_active": True,
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(template_create.status_code, status.HTTP_201_CREATED)
        template_id = template_create.data["id"]
        self.assertEqual(SeoMetaTemplate.objects.count(), 1)

        template_update = self.client.patch(
            reverse("seo_api:backoffice-template-detail", kwargs={"id": template_id}),
            {"is_active": False},
            format="json",
            **self.auth,
        )
        self.assertEqual(template_update.status_code, status.HTTP_200_OK)
        self.assertFalse(template_update.data["is_active"])

        override_create = self.client.post(
            reverse("seo_api:backoffice-override-list"),
            {
                "path": "/catalog/demo",
                "locale": "uk",
                "meta_title": "Demo title",
                "meta_description": "Demo description",
                "h1": "Demo H1",
                "canonical_url": "",
                "robots_directive": "index,follow",
                "og_title": "",
                "og_description": "",
                "og_image_url": "",
                "is_active": True,
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(override_create.status_code, status.HTTP_201_CREATED)
        override_id = override_create.data["id"]
        self.assertEqual(SeoMetaOverride.objects.count(), 1)

        override_delete = self.client.delete(
            reverse("seo_api:backoffice-override-detail", kwargs={"id": override_id}),
            **self.auth,
        )
        self.assertEqual(override_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(SeoMetaOverride.objects.count(), 0)

    def test_public_config_and_resolve_meta(self):
        SeoMetaTemplate.objects.create(
            entity_type="page",
            locale="uk",
            title_template="{name} | {site_name}",
            description_template="{name}",
            h1_template="{name}",
            og_title_template="{name}",
            og_description_template="{name}",
            is_active=True,
        )

        config_response = self.client.get(reverse("seo_api:public-config"))
        self.assertEqual(config_response.status_code, status.HTTP_200_OK)
        self.assertIn("settings", config_response.data)
        self.assertIn("google", config_response.data)

        resolve_response = self.client.get(
            reverse("seo_api:public-resolve-meta"),
            {
                "path": "/catalog",
                "locale": "uk",
                "entity_type": "page",
            },
        )
        self.assertEqual(resolve_response.status_code, status.HTTP_200_OK)
        self.assertIn("meta_title", resolve_response.data)

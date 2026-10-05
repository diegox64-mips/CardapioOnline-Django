from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Category, Order, Product, StoreAvailability, StoreSettings


class OrderWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.first()
        cls.product = Product.objects.create(
            name="Brownie",
            category=cls.category,
            description="Teste",
            price="10.00",
        )
        cls.confectioner_group, _ = Group.objects.get_or_create(name="Confeiteiro")

    def setUp(self):
        self.receipt_directory = TemporaryDirectory()
        self.private_storage_settings = override_settings(PRIVATE_RECEIPTS_ROOT=Path(self.receipt_directory.name))
        self.private_storage_settings.enable()
        self.addCleanup(self.private_storage_settings.disable)
        self.addCleanup(self.receipt_directory.cleanup)
        self.store_settings = StoreSettings.objects.get(pk=1)
        self.store_settings.whatsapp_number = "0000000000"
        self.store_settings.minimum_order = "0.00"
        self.store_settings.save()

    def checkout_data(self, delivery=False):
        customer = {"customer_name": "Cliente de teste"}
        if delivery:
            customer.update({
                "cep": "12345-678",
                "street": "Rua de teste",
                "number": "10",
                "complement": "Casa 2",
                "neighborhood": "Centro",
                "city": "Cidade de demonstração",
                "state": "SP",
            })
        return {
            "items": [{"id": self.product.pk, "qtd": 2}],
            "delivery": delivery,
            "coupon": "",
            "customer": customer,
        }

    def quote(self, data=None):
        payload = data or self.checkout_data()
        return self.client.post(reverse("validate_order"), payload, content_type="application/json")

    def final_payload(self, proof_method="whatsapp", data=None, quote=None, request_token=None):
        payload = dict(data or self.checkout_data())
        quote = quote or self.quote(payload)
        payload.update({
            "request_token": str(request_token or uuid4()),
            "quote_token": quote.json()["quote_token"],
            "proof_method": proof_method,
        })
        return payload

    def submit_json(self, payload):
        return self.client.post(reverse("submit_order"), payload, content_type="application/json")

    def png_receipt(self, name="receipt.png"):
        image_file = BytesIO()
        Image.new("RGB", (2, 2), color="white").save(image_file, format="PNG")
        return SimpleUploadedFile(name, image_file.getvalue(), content_type="image/png")

    def submit_upload(self, payload, receipt=None):
        body = {"payload": __import__("json").dumps(payload)}
        if receipt:
            body["receipt"] = receipt
        return self.client.post(reverse("submit_order"), body)

    def test_quote_does_not_create_an_order(self):
        response = self.quote()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], "20.00")
        self.assertIn("quote_token", response.json())
        self.assertFalse(Order.objects.exists())

    def test_whatsapp_choice_saves_order_and_shares_reference(self):
        payload = self.final_payload("whatsapp")
        response = self.submit_json(payload)
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get()
        self.assertEqual(order.status, Order.Status.AWAITING_WHATSAPP)
        self.assertIn(order.reference, response.json()["message"])
        self.assertIn("Doces da Malu", response.json()["message"])
        self.assertIn(order.reference, response.json()["whatsapp_url"] or response.json()["message"])
        self.assertEqual(response.json()["whatsapp_url"].split("/")[3].split("?")[0], "0000000000")

    def test_upload_saves_private_receipt_and_returns_reference(self):
        payload = self.final_payload("upload")
        response = self.submit_upload(payload, self.png_receipt())
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get()
        self.assertEqual(order.status, Order.Status.PROOF_UPLOADED)
        self.assertTrue(Path(order.receipt.path).is_relative_to(Path(self.receipt_directory.name)))
        self.assertNotIn("receipt_url", response.json())
        self.assertNotIn("receipt", response.json())
        with self.assertRaises(ValueError):
            order.receipt.url

    def test_whatsapp_is_optional_when_customer_uploads_proof(self):
        self.store_settings.whatsapp_number = ""
        self.store_settings.save()
        payload = self.final_payload("upload")
        self.assertEqual(self.submit_upload(payload, self.png_receipt()).status_code, 201)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(self.submit_json(self.final_payload("whatsapp")).status_code, 503)

    def test_invalid_and_oversized_receipts_are_rejected_without_saving(self):
        invalid = self.final_payload("upload")
        bad_file = SimpleUploadedFile("receipt.txt", b"not a receipt", content_type="text/plain")
        self.assertEqual(self.submit_upload(invalid, bad_file).status_code, 400)
        oversized = self.final_payload("upload")
        large_file = SimpleUploadedFile("receipt.png", b"x" * (5 * 1024 * 1024 + 1), content_type="image/png")
        self.assertEqual(self.submit_upload(oversized, large_file).status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_same_attempt_is_idempotent_and_bound_to_session(self):
        payload = self.final_payload("whatsapp")
        first = self.submit_json(payload)
        retry = self.submit_json(payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(first.json()["order_reference"], retry.json()["order_reference"])
        self.assertEqual(Order.objects.count(), 1)

        other_session = Client().post(reverse("submit_order"), payload, content_type="application/json")
        self.assertEqual(other_session.status_code, 404)
        self.assertNotIn("Cliente de teste", other_session.content.decode())

    def test_changed_price_after_quote_requires_reconfirmation(self):
        payload = self.final_payload("whatsapp")
        Product.objects.filter(pk=self.product.pk).update(price="12.00")
        response = self.submit_json(payload)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Order.objects.exists())

    def test_delivery_requires_address_and_pickup_keeps_it_empty(self):
        invalid_data = self.checkout_data(delivery=True)
        invalid_data["customer"] = {"customer_name": "Cliente de teste"}
        self.assertEqual(self.quote(invalid_data).status_code, 400)
        self.assertFalse(Order.objects.exists())

        delivery_payload = self.final_payload("whatsapp", self.checkout_data(delivery=True))
        self.assertEqual(self.submit_json(delivery_payload).status_code, 201)
        self.assertIn("CEP 12345-678", Order.objects.get().address)

        Order.objects.all().delete()
        pickup_payload = self.final_payload("whatsapp", self.checkout_data())
        self.assertEqual(self.submit_json(pickup_payload).status_code, 201)
        self.assertEqual(Order.objects.get().address, "")

    def test_confectioner_group_can_login_but_regular_user_cannot(self):
        user_model = get_user_model()
        confectioner = user_model.objects.create_user(username="confeiteira", password="test-password")
        confectioner.groups.add(self.confectioner_group)
        response = self.client.post(reverse("confectioner_login"), {"username": "confeiteira", "password": "test-password"})
        self.assertRedirects(response, reverse("confectioner_orders"))
        self.assertFalse(confectioner.is_staff)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

        other_client = Client()
        user_model.objects.create_user(username="cliente", password="test-password")
        denied_login = other_client.post(reverse("confectioner_login"), {"username": "cliente", "password": "test-password"})
        self.assertEqual(denied_login.status_code, 200)
        self.assertNotIn("_auth_user_id", other_client.session)

    def test_django_admin_profile_selector_creates_the_right_access(self):
        user_model = get_user_model()
        administrator = user_model.objects.create_superuser(username="admin-profile-test", password="T0rtas!Seguro-704-Perfil")
        self.client.force_login(administrator)
        add_url = reverse("admin:auth_user_add")
        self.assertContains(self.client.get(add_url), "Perfil")

        confectioner_password = "B0los!Seguro-517-Confeiteiro"
        response = self.client.post(add_url, {
            "username": "novo-confeiteiro",
            "password1": confectioner_password,
            "password2": confectioner_password,
            "profile": "confectioner",
            "_save": "Salvar",
        })
        self.assertEqual(response.status_code, 302)
        confectioner = user_model.objects.get(username="novo-confeiteiro")
        self.assertFalse(confectioner.is_staff)
        self.assertFalse(confectioner.is_superuser)
        self.assertTrue(confectioner.groups.filter(name="Confeiteiro").exists())

        admin_password = "D0ces!Seguro-830-Admin"
        response = self.client.post(add_url, {
            "username": "novo-admin",
            "password1": admin_password,
            "password2": admin_password,
            "profile": "administrator",
            "_save": "Salvar",
        })
        self.assertEqual(response.status_code, 302)
        django_admin = user_model.objects.get(username="novo-admin")
        self.assertTrue(django_admin.is_staff)
        self.assertTrue(django_admin.is_superuser)
        self.assertFalse(django_admin.groups.filter(name="Confeiteiro").exists())

    def test_orders_and_receipts_are_private_and_status_requires_post(self):
        payload = self.final_payload("upload")
        self.assertEqual(self.submit_upload(payload, self.png_receipt()).status_code, 201)
        order = Order.objects.get()
        orders_url = reverse("confectioner_orders")
        receipt_url = reverse("confectioner_receipt", args=[order.pk])
        self.assertEqual(Client().get(orders_url).status_code, 302)
        self.assertEqual(Client().get(receipt_url).status_code, 302)

        user_model = get_user_model()
        confectioner = user_model.objects.create_user(username="staff", password="test-password")
        confectioner.groups.add(self.confectioner_group)
        self.client.force_login(confectioner)
        self.assertContains(self.client.get(orders_url), order.reference)
        self.assertEqual(self.client.get(receipt_url).status_code, 200)
        self.assertIn("attachment", self.client.get(receipt_url).headers["Content-Disposition"])
        status_url = reverse("confectioner_status", args=[order.pk])
        self.assertEqual(self.client.get(status_url).status_code, 405)
        self.assertEqual(self.client.post(status_url, {"status": Order.Status.CONFIRMED}).status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)

    def test_status_post_requires_csrf(self):
        order = Order.objects.create(
            request_token=uuid4(), request_hash="a" * 64, owner_hash="b" * 64,
            customer_name="Cliente", items=[], subtotal="0", discount="0", delivery_fee="0", total="0",
            proof_method=Order.ProofMethod.WHATSAPP, status=Order.Status.AWAITING_WHATSAPP,
        )
        user_model = get_user_model()
        confectioner = user_model.objects.create_user(username="csrf-staff", password="test-password")
        confectioner.groups.add(self.confectioner_group)
        client = Client(enforce_csrf_checks=True)
        client.force_login(confectioner)
        response = client.post(reverse("confectioner_status", args=[order.pk]), {"status": Order.Status.CONFIRMED})
        self.assertEqual(response.status_code, 403)

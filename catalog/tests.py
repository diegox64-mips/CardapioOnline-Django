import json
from decimal import Decimal
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse

from .models import Category, Coupon, Product, StoreAvailability, StoreSettings


class CheckoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.first()
        cls.product = Product.objects.create(name="Doce teste", category=category, description="Teste", price="10.00")
        cls.coupon = Coupon.objects.create(code="easteregg", discount_percent="15.00")

    def setUp(self):
        self.settings = StoreSettings.objects.get(pk=1)
        self.settings.delivery_fee = Decimal("7.50")
        self.settings.minimum_order = Decimal("20.00")
        self.settings.whatsapp_number = "0000000000"
        self.settings.save()

    def order(self, quantity=2, **kwargs):
        customer = {"customer_name": "Cliente teste"}
        if kwargs.get("delivery", False):
            customer.update({"cep": "12345-678", "street": "Rua teste", "number": "1", "neighborhood": "Centro", "city": "Cidade de demonstração", "state": "SP"})
        data = {
            "items": [{"id": self.product.pk, "qtd": quantity}],
            "delivery": False,
            "coupon": "",
            "customer": customer,
        }
        data.update(kwargs)
        return self.client.post(reverse("validate_order"), data, content_type="application/json")

    def submit_order(self, quantity=2, proof_method="whatsapp", receipt=None, **kwargs):
        quote = self.order(quantity, **kwargs)
        if quote.status_code != 200:
            return quote
        data = {
            "items": [{"id": self.product.pk, "qtd": quantity}],
            "delivery": False,
            "coupon": "",
            "customer": {"customer_name": "Cliente teste"},
        }
        if kwargs.get("delivery", False):
            data["customer"].update({"cep": "12345-678", "street": "Rua teste", "number": "1", "neighborhood": "Centro", "city": "Cidade de demonstração", "state": "SP"})
        data.update(kwargs)
        data.update({"request_token": str(uuid4()), "quote_token": quote.json()["quote_token"], "proof_method": proof_method})
        if proof_method == "upload":
            return self.client.post(reverse("submit_order"), {"payload": json.dumps(data), "receipt": receipt})
        return self.client.post(reverse("submit_order"), data, content_type="application/json")

    def test_below_minimum_rejected_even_with_delivery(self):
        response = self.order(1, delivery=True, total="1000", minimum_order=0)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Faltam R$ 10,00", response.json()["error"])

    def test_exact_minimum_and_delivery_from_database(self):
        response = self.order(delivery=True, delivery_fee=0)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.json()["total"]), Decimal("27.50"))

    def test_pickup(self):
        self.assertEqual(Decimal(self.order().json()["total"]), Decimal("20"))

    def test_discount_counts_toward_minimum(self):
        self.assertEqual(self.order(coupon="easteregg").status_code, 400)
        response = self.order(3, coupon="easteregg", delivery=True)
        self.assertEqual(Decimal(response.json()["total"]), Decimal("33"))

    def test_admin_coupon_applies_configured_percentage(self):
        Coupon.objects.create(code=" sweets25 ", discount_percent="25.00")
        response = self.submit_order(4, coupon="sweets25")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.json()["total"]), Decimal("30.00"))
        self.assertIn("Cupom: SWEETS25", response.json()["message"])

    def test_inactive_coupon_is_rejected(self):
        self.coupon.is_active = False
        self.coupon.save()
        self.assertEqual(self.order(coupon="easteregg").status_code, 400)
        self.assertEqual(self.client.post(reverse("validate_coupon"), {"code": "easteregg"}, content_type="application/json").status_code, 404)

    def test_coupon_endpoint_returns_admin_configured_discount(self):
        response = self.client.post(reverse("validate_coupon"), {"code": "eAsTeReGg"}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"code": "EASTEREGG", "discount_percent": "15.00"})
        self.assertEqual(self.client.get(reverse("validate_coupon")).status_code, 405)

    def test_free_delivery_still_identified_as_delivery(self):
        self.settings.delivery_fee = 0
        self.settings.save()
        response = self.submit_order(delivery=True)
        self.assertIn("Desejo entrega.", response.json()["message"])
        self.assertEqual(Decimal(response.json()["total"]), Decimal("20"))

    def test_current_price_and_settings_used(self):
        Product.objects.filter(pk=self.product.pk).update(price="4.00")
        self.assertEqual(self.order().status_code, 400)

    def test_empty_invalid_and_unavailable_items(self):
        for items in [[], [{"id": self.product.pk, "qtd": 0}], [{"id": self.product.pk, "qtd": 100}], [{"id": True, "qtd": 2}], [{"id": 999999, "qtd": 1}]]:
            with self.subTest(items=items):
                self.assertEqual(self.order(items=items).status_code, 400)
        Product.objects.filter(pk=self.product.pk).update(is_active=False)
        self.assertEqual(self.order().status_code, 400)

    def test_malformed_json_and_method(self):
        self.assertEqual(self.client.post(reverse("validate_order"), "{", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.get(reverse("validate_order")).status_code, 405)

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("validate_order"), {}, content_type="application/json").status_code, 403)
        client.get(reverse("cart"))
        response = client.post(reverse("validate_order"), {"items": [{"id": self.product.pk, "qtd": 2}], "customer": {"customer_name": "Cliente teste"}}, content_type="application/json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200)

    def test_settings_validation_and_registration(self):
        self.assertIn(StoreSettings, admin.site._registry)
        self.assertIn(Coupon, admin.site._registry)
        settings_admin = admin.site._registry[StoreSettings]
        self.assertIn(StoreAvailability, [inline.model for inline in settings_admin.inlines])
        self.settings.whatsapp_number = "not-a-number"
        with self.assertRaises(ValidationError):
            self.settings.full_clean()
        self.settings.whatsapp_number = "0000000000"
        self.settings.delivery_fee = -1
        with self.assertRaises(ValidationError):
            self.settings.full_clean()
        self.settings.delivery_fee = 0
        self.settings.minimum_order = -1
        with self.assertRaises(ValidationError):
            self.settings.full_clean()

    def test_menu_uses_whatsapp_number_from_store_settings(self):
        response = self.client.get(reverse("menu"))
        self.assertContains(response, "https://wa.me/0000000000")
        self.assertContains(response, "tel:+0000000000")

    def test_admin_controls_social_links_and_weekly_availability(self):
        self.settings.facebook_url = "https://facebook.example/doces-da-malu-demo"
        self.settings.instagram_url = "https://instagram.example/doces-da-malu-demo"
        self.settings.save()
        monday = StoreAvailability.objects.get(store_settings=self.settings, weekday=1)
        monday.is_open = True
        monday.hours = "11h às 17h"
        monday.save()

        response = self.client.get(reverse("menu"))
        self.assertContains(response, "https://facebook.example/doces-da-malu-demo", count=2)
        self.assertContains(response, "https://instagram.example/doces-da-malu-demo", count=2)
        self.assertContains(response, "Doces da Malu")
        self.assertContains(response, "11h às 17h")
        self.assertContains(response, "Fechado")
        self.assertEqual(StoreAvailability.objects.filter(store_settings=self.settings).count(), 7)

    def test_open_availability_requires_hours(self):
        availability = StoreAvailability.objects.get(store_settings=self.settings, weekday=0)
        availability.is_open = True
        availability.hours = ""
        with self.assertRaises(ValidationError):
            availability.full_clean()

    def test_cart_receives_array_and_configured_prices(self):
        response = self.client.get(reverse("cart"))
        self.assertContains(response, "ENTREGA (+ R$ 7,50)")
        self.assertContains(response, "Ir para pagamento")
        self.assertContains(response, 'id="paymentStep" class="payment-step" hidden')
        self.assertContains(response, "/static/img/payment-demo.svg")
        self.assertContains(response, "não transfira valores")
        self.assertContains(response, "escolha como enviar o comprovante")
        self.assertIsInstance(response.context["products_json"], list)
        self.assertEqual(response.context["checkout_settings"]["minimum_order"], "20.00")
        self.assertTrue(response.context["checkout_settings"]["whatsapp_configured"])
        self.assertContains(response, "data-validation-url=\"/cart/coupon/\"")

    def test_zero_minimum_still_rejects_empty_cart(self):
        self.settings.minimum_order = 0
        self.settings.save()
        self.assertEqual(self.order(1).status_code, 200)
        self.assertEqual(self.order(items=[]).status_code, 400)

    def test_whatsapp_message_and_destination(self):
        Product.objects.filter(pk=self.product.pk).update(name="Doce de limão & chocolate + 50%")
        response = self.submit_order(delivery=True)
        data = response.json()
        url = urlparse(data["whatsapp_url"])
        self.assertEqual(url.scheme, "https")
        self.assertEqual(url.netloc, "wa.me")
        self.assertEqual(url.path, "/0000000000")
        self.assertEqual(parse_qs(url.query)["text"], [data["message"]])
        self.assertIn("2 x Doce de limão & chocolate + 50% — R$ 10,00 cada = R$ 20,00", data["message"])
        self.assertIn("Entrega: R$ 7,50", data["message"])
        self.assertIn("Total: R$ 27,50", data["message"])
        self.assertIn("enviarei o comprovante de pagamento por aqui", data["message"])

    def test_no_whatsapp_link_for_rejected_order(self):
        self.assertNotIn("whatsapp_url", self.order(1).json())

    def test_order_requires_whatsapp_configured_in_store_settings(self):
        self.settings.whatsapp_number = ""
        self.settings.save()
        response = self.submit_order(proof_method="whatsapp")
        self.assertEqual(response.status_code, 503)
        self.assertIn("não configurou um telefone válido", response.json()["error"])

    def test_whatsapp_coupon_and_pickup(self):
        message = self.submit_order(3, coupon="easteregg").json()["message"]
        self.assertIn("Cupom: EASTEREGG", message)
        self.assertIn("Vou retirar no local", message)
        self.assertIn("Desconto: R$ 4,50", message)
        self.assertIn("Total: R$ 25,50", message)
        self.assertIn("enviarei o comprovante de pagamento por aqui", message)

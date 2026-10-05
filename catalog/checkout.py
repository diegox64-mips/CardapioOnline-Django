import hashlib
import json
import secrets
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_POST

from .forms import CheckoutCustomerForm, ReceiptUploadForm
from .models import Coupon, Order, Product, StoreSettings


class CheckoutProblem(Exception):
    def __init__(self, message, status=400):
        self.message = message
        self.status = status


def _read_payload(request):
    try:
        if request.content_type == "application/json":
            data = json.loads(request.body)
            receipt = None
        elif request.content_type.startswith("multipart/form-data"):
            data = json.loads(request.POST.get("payload", ""))
            receipt = request.FILES.get("receipt")
        else:
            raise ValueError
        if not isinstance(data, dict):
            raise ValueError
        return data, receipt
    except (ValueError, TypeError, UnicodeDecodeError):
        raise CheckoutProblem("Confira os dados da sacolinha e tente novamente.")


def _quote(data):
    items = data.get("items")
    delivery = data.get("delivery", False)
    coupon_code = data.get("coupon", "")
    customer = data.get("customer")
    if not isinstance(items, list) or not items or len(items) > 100:
        raise CheckoutProblem("Confira os itens da sacolinha.")
    if type(delivery) is not bool or not isinstance(coupon_code, str) or len(coupon_code) > 40:
        raise CheckoutProblem("Confira a forma de entrega e o cupom.")
    if not isinstance(customer, dict) or any(not isinstance(value, str) for value in customer.values()):
        raise CheckoutProblem("Informe os dados do cliente.")

    quantities = {}
    for item in items:
        if not isinstance(item, dict):
            raise CheckoutProblem("Confira os itens da sacolinha.")
        product_id, quantity = item.get("id"), item.get("qtd")
        if type(product_id) is not int or type(quantity) is not int or product_id < 1 or not 1 <= quantity <= 99:
            raise CheckoutProblem("Confira os itens e as quantidades da sacolinha.")
        quantities[product_id] = quantities.get(product_id, 0) + quantity
        if quantities[product_id] > 99:
            raise CheckoutProblem("A quantidade máxima por produto é 99.")

    form = CheckoutCustomerForm(customer, delivery=delivery)
    if not form.is_valid():
        errors = [f"{form.fields[name].label}: {error}" for name, values in form.errors.items() for error in values]
        raise CheckoutProblem(" ".join(errors))

    products = sorted(Product.objects.filter(pk__in=quantities, is_active=True), key=lambda product: product.pk)
    if len(products) != len(quantities):
        raise CheckoutProblem("Um produto não está mais disponível. Atualize a sacolinha.")

    coupon = None
    if coupon_code.strip():
        coupon = Coupon.objects.filter(code__iexact=coupon_code.strip(), is_active=True).first()
        if not coupon:
            raise CheckoutProblem("O cupom informado não está mais ativo. Confira o código e tente novamente.")

    store_settings = StoreSettings.objects.first() or StoreSettings()
    subtotal = sum((product.price * quantities[product.pk] for product in products), Decimal("0"))
    rate = coupon.discount_percent / Decimal("100") if coupon else Decimal("0")
    discount = (subtotal * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    fee = store_settings.delivery_fee if delivery else Decimal("0")
    total = subtotal - discount + fee
    if subtotal - discount < store_settings.minimum_order:
        missing = store_settings.minimum_order - (subtotal - discount)
        missing_text = f"{missing:.2f}".replace(".", ",")
        raise CheckoutProblem(f"Pedido mínimo não atingido. Faltam R$ {missing_text} em produtos após descontos, sem entrega.")

    snapshot = [
        {
            "product_id": product.pk,
            "name": product.name,
            "quantity": quantities[product.pk],
            "unit_price": f"{product.price:.2f}",
            "line_total": f"{product.price * quantities[product.pk]:.2f}",
        }
        for product in products
    ]
    canonical_data = {
        "items": snapshot,
        "delivery": delivery,
        "address": form.delivery_address(),
        "customer_name": form.cleaned_data["customer_name"],
        "coupon": coupon.code if coupon else "",
        "subtotal": f"{subtotal:.2f}",
        "discount": f"{discount:.2f}",
        "delivery_fee": f"{fee:.2f}",
        "total": f"{total:.2f}",
    }
    canonical_json = json.dumps(canonical_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fingerprint = salted_hmac("catalog.checkout.quote", canonical_json).hexdigest()
    return {
        **canonical_data,
        "fingerprint": fingerprint,
        "quote_token": signing.dumps({"fingerprint": fingerprint}, salt="catalog.checkout.quote"),
        "coupon_object": coupon,
        "store_settings": store_settings,
    }


def _money(value):
    return f"{Decimal(value):.2f}".replace(".", ",")


def _order_message(order):
    lines = [f"*Pedido {order.reference} — Doces da Malu*", f"Cliente: {order.customer_name}", "", "*Itens*"]
    for item in order.items:
        lines.append(f"- {item['quantity']} x {item['name']} — R$ {_money(item['unit_price'])} cada = R$ {_money(item['line_total'])}")
    lines.append("\nDesejo entrega." if order.delivery else "\nVou retirar no local.")
    if order.delivery:
        lines.extend(["Endereço:", order.address])
    if order.coupon:
        lines.append(f"Cupom: {order.coupon}")
    lines.extend([
        f"Produtos: R$ {_money(order.subtotal)}",
        f"Desconto: R$ {_money(order.discount)}",
        f"Entrega: R$ {_money(order.delivery_fee)}",
        f"Total: R$ {_money(order.total)}",
        "",
        "Para iniciarmos a separação, enviarei o comprovante de pagamento por aqui.",
    ])
    return "\n".join(lines)


def _order_response(order, status=200):
    result = {
        "order_reference": order.reference,
        "status": order.status,
        "total": f"{Decimal(order.total):.2f}",
    }
    if order.proof_method == Order.ProofMethod.WHATSAPP:
        message = _order_message(order)
        result["message"] = message
        result["whatsapp_url"] = "https://wa.me/" + order.whatsapp_number + "?" + urlencode({"text": message})
    else:
        result["message"] = "Pedido registrado. O comprovante foi recebido e aguarda conferência."
    return JsonResponse(result, status=status)


@require_POST
def quote_order(request):
    try:
        data, _ = _read_payload(request)
        quote = _quote(data)
    except CheckoutProblem as problem:
        return JsonResponse({"error": problem.message}, status=problem.status)
    return JsonResponse({
        "subtotal": quote["subtotal"],
        "discount": quote["discount"],
        "delivery_fee": quote["delivery_fee"],
        "total": quote["total"],
        "quote_token": quote["quote_token"],
    })


@require_POST
def submit_order(request):
    try:
        data, receipt = _read_payload(request)
        quote = _quote(data)
        request_token = UUID(str(data.get("request_token", "")))
        proof_method = data.get("proof_method")
        if proof_method not in Order.ProofMethod.values:
            raise CheckoutProblem("Escolha como deseja enviar o comprovante.")
        token_data = signing.loads(data.get("quote_token", ""), salt="catalog.checkout.quote", max_age=3600)
        if token_data.get("fingerprint") != quote["fingerprint"]:
            raise CheckoutProblem("O pedido mudou desde a conferência. Confira os dados e avance novamente.", status=409)
    except (CheckoutProblem, ValueError, TypeError, BadSignature, SignatureExpired) as error:
        problem = error if isinstance(error, CheckoutProblem) else CheckoutProblem("A conferência expirou. Volte à sacolinha e tente novamente.")
        return JsonResponse({"error": problem.message}, status=problem.status)

    if proof_method == Order.ProofMethod.UPLOAD:
        form = ReceiptUploadForm(files={"receipt": receipt} if receipt else {})
        if not form.is_valid():
            errors = [str(error) for values in form.errors.values() for error in values]
            return JsonResponse({"error": " ".join(errors)}, status=400)
        receipt = form.cleaned_data["receipt"]
    else:
        if receipt:
            return JsonResponse({"error": "Remova o arquivo ou escolha anexar comprovante."}, status=400)
        number = quote["store_settings"].whatsapp_number
        if not number.isdigit() or not 10 <= len(number) <= 15:
            return JsonResponse({"error": "A loja ainda não configurou um telefone válido para pedidos no WhatsApp."}, status=503)

    receipt_hash = ""
    if receipt:
        hasher = hashlib.sha256()
        for chunk in receipt.chunks():
            hasher.update(chunk)
        receipt.seek(0)
        receipt_hash = hasher.hexdigest()

    request_fingerprint = salted_hmac(
        "catalog.order.request",
        json.dumps({"quote": quote["fingerprint"], "method": proof_method, "receipt": receipt_hash}, sort_keys=True),
    ).hexdigest()
    owner_token = request.session.get("order_owner")
    if not owner_token:
        owner_token = secrets.token_urlsafe(32)
        request.session["order_owner"] = owner_token
    owner_hash = salted_hmac("catalog.order.owner", owner_token).hexdigest()

    existing = Order.objects.filter(request_token=request_token).first()
    if existing:
        if existing.owner_hash != owner_hash:
            return JsonResponse({"error": "Não foi possível recuperar este pedido nesta sessão."}, status=404)
        if existing.request_hash != request_fingerprint:
            return JsonResponse({"error": "Esta tentativa já foi usada com outros dados. Reabra a sacolinha."}, status=409)
        return _order_response(existing)

    store_settings = quote["store_settings"]
    order = Order(
        request_token=request_token,
        request_hash=request_fingerprint,
        owner_hash=owner_hash,
        customer_name=quote["customer_name"],
        delivery=data["delivery"],
        address=quote["address"],
        items=quote["items"],
        subtotal=quote["subtotal"],
        discount=quote["discount"],
        delivery_fee=quote["delivery_fee"],
        total=quote["total"],
        coupon=quote["coupon"],
        proof_method=proof_method,
        whatsapp_number=store_settings.whatsapp_number if proof_method == Order.ProofMethod.WHATSAPP else "",
        status=Order.Status.PROOF_UPLOADED if proof_method == Order.ProofMethod.UPLOAD else Order.Status.AWAITING_WHATSAPP,
    )
    stored_receipt = ""
    try:
        with transaction.atomic():
            order.save()
            if receipt:
                extension = Path(receipt.name).suffix.lower()
                filename = secrets.token_hex(20) + extension
                storage = Order._meta.get_field("receipt").storage
                stored_receipt = storage.save(filename, receipt)
                order.receipt.name = stored_receipt
                order.save(update_fields=["receipt", "updated_at"])
    except IntegrityError:
        existing = Order.objects.filter(request_token=request_token).first()
        if stored_receipt:
            Order._meta.get_field("receipt").storage.delete(stored_receipt)
        if existing and existing.owner_hash == owner_hash and existing.request_hash == request_fingerprint:
            return _order_response(existing)
        return JsonResponse({"error": "O pedido já foi enviado. Recarregue a sacolinha para continuar."}, status=409)
    except Exception:
        if stored_receipt:
            Order._meta.get_field("receipt").storage.delete(stored_receipt)
        raise
    return _order_response(order, status=201)

import json

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .checkout import quote_order, submit_order
from .forms import CheckoutCustomerForm
from .models import Category, Coupon, Product, StoreAvailability, StoreSettings


def _products_json(products):
    data = [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price": float(p.price),
            "lastPrice": float(p.last_price),
            "type": p.category_id,
            "img": p.image.url if p.image else "",
        }
        for p in products
    ]
    return data


def menu_view(request):
    products = Product.objects.filter(is_active=True).select_related("category")
    settings = StoreSettings.objects.first() or StoreSettings()
    whatsapp_number = settings.whatsapp_number if settings.whatsapp_number.isdigit() and 10 <= len(settings.whatsapp_number) <= 15 else ""
    context = {
        "products": products,
        "categories": Category.objects.all(),
        "products_json": _products_json(products),
        "whatsapp_number": whatsapp_number,
        "facebook_url": settings.facebook_url,
        "instagram_url": settings.instagram_url,
        "store_availability": StoreAvailability.objects.filter(store_settings_id=settings.pk),
    }
    return render(request, "index.html", context)


def cart_view(request):
    products = Product.objects.filter(is_active=True).select_related("category")
    settings = StoreSettings.objects.first() or StoreSettings()
    return render(request, "cart.html", {
        "products": products,
        "products_json": _products_json(products),
        "store_settings": settings,
        "customer_form": CheckoutCustomerForm(),
        "checkout_settings": {
            "delivery_fee": str(settings.delivery_fee),
            "minimum_order": str(settings.minimum_order),
            "whatsapp_configured": settings.whatsapp_number.isdigit() and 10 <= len(settings.whatsapp_number) <= 15,
        },
    })


@require_POST
def validate_coupon(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or not isinstance(data.get("code"), str):
            raise ValueError
        code = data["code"].strip()
        if not code or len(code) > 40:
            raise ValueError
    except (ValueError, TypeError, UnicodeDecodeError):
        return JsonResponse({"error": "Informe um código de cupom válido."}, status=400)

    coupon = Coupon.objects.filter(code__iexact=code, is_active=True).first()
    if not coupon:
        return JsonResponse({"error": "Cupom inválido ou inativo."}, status=404)
    return JsonResponse({"code": coupon.code, "discount_percent": str(coupon.discount_percent)})


def validate_order(request):
    return quote_order(request)

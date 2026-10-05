from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils.html import format_html

from .models import Category, Coupon, Order, Product, StoreAvailability, StoreSettings


class UserProfileCreationForm(UserCreationForm):
    profile = forms.ChoiceField(
        label="Perfil",
        choices=[("confectioner", "Confeiteiro"), ("administrator", "Administrador do Django")],
        initial="confectioner",
    )


class ProfileUserAdmin(UserAdmin):
    add_form = UserProfileCreationForm
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "password1", "password2", "profile")}),
    )

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def save_model(self, request, obj, form, change):
        if not change:
            is_administrator = form.cleaned_data["profile"] == "administrator"
            obj.is_staff = is_administrator
            obj.is_superuser = is_administrator
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if not change:
            user = form.instance
            if form.cleaned_data["profile"] == "confectioner":
                group, _ = Group.objects.get_or_create(name="Confeiteiro")
                user.groups.set([group])
            else:
                user.groups.clear()


User = get_user_model()
if User in admin.site._registry:
    admin.site.unregister(User)
admin.site.register(User, ProfileUserAdmin)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "last_price", "is_active", "created_at"]
    list_filter = ["category", "is_active"]
    search_fields = ["name", "description", "category__name"]
    list_select_related = ["category"]
    readonly_fields = ["created_at", "updated_at"]


class StoreAvailabilityInline(admin.TabularInline):
    model = StoreAvailability
    extra = 0
    ordering = ("weekday",)
    fields = ["weekday", "is_open", "hours"]


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = ["__str__", "delivery_fee", "minimum_order", "whatsapp_number"]
    inlines = [StoreAvailabilityInline]

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not StoreSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ["code", "discount_percent", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["code"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["reference", "customer_name", "created_at", "total", "proof_method_label", "status"]
    list_filter = ["status", "proof_method", "delivery", "created_at"]
    search_fields = ["customer_name", "coupon"]
    date_hierarchy = "created_at"
    readonly_fields = [
        "reference", "request_token", "customer_name", "delivery", "address", "items",
        "subtotal", "discount", "delivery_fee", "total", "coupon", "proof_method",
        "whatsapp_number", "created_at", "updated_at", "receipt_download",
    ]
    fields = readonly_fields + ["status"]

    @admin.display(description="Forma de envio")
    def proof_method_label(self, obj):
        return obj.get_proof_method_display()

    @admin.display(description="Comprovante")
    def receipt_download(self, obj):
        if not obj.receipt:
            return "Nenhum comprovante anexado"
        url = reverse("confectioner_receipt", args=[obj.pk])
        return format_html('<a href="{}">Baixar comprovante</a>', url)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

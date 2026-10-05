from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from .storage import PrivateReceiptStorage


class Category(models.Model):
    name = models.CharField("Nome", max_length=80, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=120)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Categoria",
    )
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    last_price = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    image = models.ImageField(
        upload_to="products/%Y/%m/",
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"])],
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name

    @property
    def on_promotion(self):
        return self.last_price and self.last_price > 0


class StoreSettings(models.Model):
    delivery_fee = models.DecimalField("Taxa de entrega", max_digits=8, decimal_places=2, default=3, validators=[MinValueValidator(0)])
    minimum_order = models.DecimalField(
        "Valor mínimo do pedido", max_digits=8, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
        help_text="Valor dos produtos após descontos, sem a taxa de entrega. Zero desativa o mínimo.",
    )
    whatsapp_number = models.CharField(
        "WhatsApp para pedidos",
        max_length=15,
        default="",
        blank=True,
        validators=[RegexValidator(r"^\d{10,15}$", "Informe DDI, DDD e telefone usando apenas números.")],
        help_text="Inclua DDI e DDD, usando apenas números, sem espaços ou símbolos.",
    )
    facebook_url = models.URLField("Link do Facebook", blank=True, default="")
    instagram_url = models.URLField("Link do Instagram", blank=True, default="")

    class Meta:
        verbose_name = "Configuração da loja"
        verbose_name_plural = "Configurações da loja"
        constraints = [models.CheckConstraint(condition=models.Q(pk=1), name="store_settings_singleton")]

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Contato, redes sociais e loja"


class Coupon(models.Model):
    code = models.CharField("Código", max_length=40, unique=True)
    discount_percent = models.DecimalField(
        "Desconto (%)",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.01), MaxValueValidator(100)],
    )
    is_active = models.BooleanField("Ativo", default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Cupom promocional"
        verbose_name_plural = "Cupons promocionais"

    def clean(self):
        self.code = self.code.strip().upper()
        super().clean()

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} ({self.discount_percent}%)"


class StoreAvailability(models.Model):
    WEEKDAYS = [
        (0, "Domingo"),
        (1, "Segunda-feira"),
        (2, "Terça-feira"),
        (3, "Quarta-feira"),
        (4, "Quinta-feira"),
        (5, "Sexta-feira"),
        (6, "Sábado"),
    ]

    store_settings = models.ForeignKey(StoreSettings, on_delete=models.CASCADE, related_name="availability")
    weekday = models.PositiveSmallIntegerField("Dia da semana", choices=WEEKDAYS)
    is_open = models.BooleanField("Aberto", default=False)
    hours = models.CharField("Horário", max_length=40, blank=True)

    class Meta:
        ordering = ["weekday"]
        constraints = [models.UniqueConstraint(fields=["store_settings", "weekday"], name="unique_store_availability_day")]
        verbose_name = "Disponibilidade"
        verbose_name_plural = "Disponibilidade semanal"

    def clean(self):
        if self.is_open and not self.hours.strip():
            raise ValidationError({"hours": "Informe o horário de atendimento do dia aberto."})
        super().clean()

    def __str__(self):
        return self.get_weekday_display()


class Order(models.Model):
    class ProofMethod(models.TextChoices):
        UPLOAD = "upload", "Comprovante anexado"
        WHATSAPP = "whatsapp", "Enviar pelo WhatsApp"

    class Status(models.TextChoices):
        AWAITING_WHATSAPP = "awaiting_whatsapp", "Aguardando comprovante via WhatsApp"
        PROOF_UPLOADED = "proof_uploaded", "Comprovante anexado — conferir"
        CONFIRMED = "confirmed", "Pagamento confirmado"
        CANCELLED = "cancelled", "Cancelado"

    request_token = models.UUIDField(unique=True, editable=False)
    request_hash = models.CharField(max_length=64, editable=False)
    owner_hash = models.CharField(max_length=64, editable=False)
    customer_name = models.CharField("Cliente", max_length=120)
    delivery = models.BooleanField("Entrega", default=False)
    address = models.TextField("Endereço", blank=True)
    items = models.JSONField("Itens", default=list)
    subtotal = models.DecimalField("Produtos", max_digits=12, decimal_places=2)
    discount = models.DecimalField("Desconto", max_digits=12, decimal_places=2)
    delivery_fee = models.DecimalField("Taxa de entrega", max_digits=12, decimal_places=2)
    total = models.DecimalField("Total", max_digits=12, decimal_places=2)
    coupon = models.CharField("Cupom", max_length=40, blank=True)
    proof_method = models.CharField("Envio do comprovante", max_length=12, choices=ProofMethod.choices)
    whatsapp_number = models.CharField("WhatsApp usado", max_length=15, blank=True)
    receipt = models.FileField(upload_to="", storage=PrivateReceiptStorage(), blank=True)
    status = models.CharField("Situação", max_length=24, choices=Status.choices)
    created_at = models.DateTimeField("Data", auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        indexes = [models.Index(fields=["created_at"], name="order_created_at_idx")]

    @property
    def reference(self):
        return f"DL-{self.pk:06d}"

    def __str__(self):
        return f"{self.reference} — {self.customer_name}"

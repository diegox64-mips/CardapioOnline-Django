import catalog.storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_store_availability_and_social_links"),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_token", models.UUIDField(editable=False, unique=True)),
                ("request_hash", models.CharField(editable=False, max_length=64)),
                ("owner_hash", models.CharField(editable=False, max_length=64)),
                ("customer_name", models.CharField(max_length=120, verbose_name="Cliente")),
                ("delivery", models.BooleanField(default=False, verbose_name="Entrega")),
                ("address", models.TextField(blank=True, verbose_name="Endereço")),
                ("items", models.JSONField(default=list, verbose_name="Itens")),
                ("subtotal", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Produtos")),
                ("discount", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Desconto")),
                ("delivery_fee", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Taxa de entrega")),
                ("total", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Total")),
                ("coupon", models.CharField(blank=True, max_length=40, verbose_name="Cupom")),
                ("proof_method", models.CharField(choices=[("upload", "Comprovante anexado"), ("whatsapp", "Enviar pelo WhatsApp")], max_length=12, verbose_name="Envio do comprovante")),
                ("whatsapp_number", models.CharField(blank=True, max_length=15, verbose_name="WhatsApp usado")),
                ("receipt", models.FileField(blank=True, storage=catalog.storage.PrivateReceiptStorage(), upload_to="")),
                ("status", models.CharField(choices=[("awaiting_whatsapp", "Aguardando comprovante via WhatsApp"), ("proof_uploaded", "Comprovante anexado — conferir"), ("confirmed", "Pagamento confirmado"), ("cancelled", "Cancelado")], max_length=24, verbose_name="Situação")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Data")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Pedido",
                "verbose_name_plural": "Pedidos",
                "ordering": ["-created_at", "-pk"],
                "indexes": [models.Index(fields=["created_at"], name="order_created_at_idx")],
            },
        ),
    ]

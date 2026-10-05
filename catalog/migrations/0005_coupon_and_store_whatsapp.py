import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_default_store_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="storesettings",
            name="whatsapp_number",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Inclua DDI e DDD, usando apenas números, sem espaços ou símbolos.",
                max_length=15,
                validators=[django.core.validators.RegexValidator("^\\d{10,15}$", "Informe DDI, DDD e telefone usando apenas números.")],
                verbose_name="WhatsApp para pedidos",
            ),
        ),
        migrations.CreateModel(
            name="Coupon",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="Código")),
                (
                    "discount_percent",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=5,
                        validators=[django.core.validators.MinValueValidator(0.01), django.core.validators.MaxValueValidator(100)],
                        verbose_name="Desconto (%)",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="Ativo")),
            ],
            options={
                "verbose_name": "Cupom promocional",
                "verbose_name_plural": "Cupons promocionais",
                "ordering": ["code"],
            },
        ),
    ]

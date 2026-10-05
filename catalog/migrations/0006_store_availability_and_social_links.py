import django.db.models.deletion
from django.db import migrations, models


def create_default_availability(apps, schema_editor):
    database = schema_editor.connection.alias
    settings = apps.get_model("catalog", "StoreSettings").objects.using(database).get(pk=1)
    availability_model = apps.get_model("catalog", "StoreAvailability")
    open_days = {0, 3, 4, 5, 6}
    availability_model.objects.using(database).bulk_create([
        availability_model(
            store_settings_id=settings.pk,
            weekday=weekday,
            is_open=weekday in open_days,
            hours="19h às 00h" if weekday in open_days else "",
        )
        for weekday in range(7)
    ])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_coupon_and_store_whatsapp"),
    ]

    operations = [
        migrations.AddField(
            model_name="storesettings",
            name="facebook_url",
            field=models.URLField(blank=True, default="", verbose_name="Link do Facebook"),
        ),
        migrations.AddField(
            model_name="storesettings",
            name="instagram_url",
            field=models.URLField(blank=True, default="", verbose_name="Link do Instagram"),
        ),
        migrations.CreateModel(
            name="StoreAvailability",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "store_settings",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="availability", to="catalog.storesettings"),
                ),
                ("weekday", models.PositiveSmallIntegerField(choices=[(0, "Domingo"), (1, "Segunda-feira"), (2, "Terça-feira"), (3, "Quarta-feira"), (4, "Quinta-feira"), (5, "Sexta-feira"), (6, "Sábado")], verbose_name="Dia da semana")),
                ("is_open", models.BooleanField(default=False, verbose_name="Aberto")),
                ("hours", models.CharField(blank=True, max_length=40, verbose_name="Horário")),
            ],
            options={
                "verbose_name": "Disponibilidade",
                "verbose_name_plural": "Disponibilidade semanal",
                "ordering": ["weekday"],
                "constraints": [models.UniqueConstraint(fields=("store_settings", "weekday"), name="unique_store_availability_day")],
            },
        ),
        migrations.RunPython(create_default_availability, migrations.RunPython.noop),
    ]

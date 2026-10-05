from pathlib import Path
import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


class ConfectionerLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not (user.is_superuser or user.groups.filter(name="Confeiteiro").exists()):
            raise ValidationError("Este usuário não tem acesso à área de confeitaria.", code="not_confectioner")


class CheckoutCustomerForm(forms.Form):
    STATES = [(state, state) for state in "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()]

    customer_name = forms.CharField(label="Seu nome", min_length=2, max_length=120)
    cep = forms.CharField(label="CEP", max_length=9, required=False)
    street = forms.CharField(label="Rua", max_length=160, required=False)
    number = forms.CharField(label="Número (ou S/N)", max_length=20, required=False)
    complement = forms.CharField(label="Complemento", max_length=120, required=False)
    neighborhood = forms.CharField(label="Bairro", max_length=100, required=False)
    city = forms.CharField(label="Cidade", max_length=100, initial="", required=False)
    state = forms.ChoiceField(label="UF", choices=[("", "Selecione")] + STATES, required=False)

    def __init__(self, *args, delivery=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.delivery = delivery
        if delivery:
            for name in ("cep", "street", "number", "neighborhood", "city", "state"):
                self.fields[name].required = True

    def clean_cep(self):
        value = self.cleaned_data.get("cep", "")
        if self.delivery and not re.fullmatch(r"[0-9]{5}-?[0-9]{3}", value):
            raise ValidationError("Informe um CEP com 8 dígitos, como 12345-678.")
        return value.replace("-", "")

    def delivery_address(self):
        if not self.delivery:
            return ""
        data = self.cleaned_data
        parts = [f"{data['street']}, {data['number']}"]
        if data["complement"]:
            parts.append(data["complement"])
        parts.extend([data["neighborhood"], f"{data['city']} - {data['state']}", f"CEP {data['cep'][:5]}-{data['cep'][5:]}"])
        return "\n".join(parts)


class ReceiptUploadForm(forms.Form):
    MAX_SIZE = 5 * 1024 * 1024
    receipt = forms.FileField(label="Comprovante")

    def clean_receipt(self):
        upload = self.cleaned_data["receipt"]
        extension = Path(upload.name).suffix.lower()
        if upload.size > self.MAX_SIZE:
            raise ValidationError("O comprovante deve ter no máximo 5 MB.")
        if extension not in {".jpg", ".jpeg", ".png", ".pdf"}:
            raise ValidationError("Envie um arquivo JPG, PNG ou PDF.")
        try:
            upload.seek(0)
            if extension == ".pdf":
                if upload.read(5) != b"%PDF-":
                    raise ValidationError("O arquivo não parece ser um PDF válido.")
            else:
                with Image.open(upload) as image:
                    if image.format not in {"JPEG", "PNG"}:
                        raise ValidationError("Envie uma imagem JPG ou PNG válida.")
                    image.verify()
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
            raise ValidationError("O arquivo de imagem não pôde ser lido.")
        finally:
            upload.seek(0)
        return upload

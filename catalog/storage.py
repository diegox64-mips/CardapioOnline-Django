from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateReceiptStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(
            file_permissions_mode=0o600,
            directory_permissions_mode=0o700,
        )

    @property
    def location(self):
        return str(settings.PRIVATE_RECEIPTS_ROOT.resolve())

    def url(self, name):
        raise ValueError("Comprovantes são privados e não possuem URL pública.")

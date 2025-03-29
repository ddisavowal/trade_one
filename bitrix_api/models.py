import os
from django.db import models

class ProductPhoto(models.Model):
    external_code = models.CharField(max_length=50, unique=True)
    preview_picture = models.ImageField(upload_to="product_photos/preview/", null=True, blank=True)

    def __str__(self):
        return f"{self.external_code}"

    def delete(self, *args, **kwargs):
        # Удаляем файл из файловой системы, если он есть
        if self.preview_picture:
            if os.path.isfile(self.preview_picture.path):
                os.remove(self.preview_picture.path)
        super().delete(*args, **kwargs)
from django.core.management.base import BaseCommand
import csv
import os
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from bitrix_api.models import ProductPhoto  # Убедись, что путь правильный

CSV_FILE_PATH = os.path.join(settings.BASE_DIR, 'bitrix_api', 'import', 'cataloge.csv')

class Command(BaseCommand):
    help = "Imports products and photos from a CSV file into Django database, clearing existing data first"

    def handle(self, *args, **options):
        csv_path = CSV_FILE_PATH
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f"CSV file not found: {csv_path}"))
            return

        # Очистка базы перед импортом
        self.stdout.write("Clearing existing products from database...")
        ProductPhoto.objects.all().delete()
        self.stdout.write("Database cleared.")

        self.stdout.write(f"Importing products from {csv_path}...")

        with open(csv_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            expected_columns = {"Внешний код", "Картинка для анонса"}
            if not expected_columns.issubset(reader.fieldnames):
                self.stdout.write(self.style.ERROR(f"CSV must contain columns: {expected_columns}"))
                return

            for row in reader:
                external_code = row["Внешний код"]
                self.stdout.write(f"Processing product with external code {external_code}...")

                # Создаём новый продукт (дубликаты не проверяем, так как база очищена)
                product = ProductPhoto(
                    external_code=external_code,
                )

                # Сохраняем фото для анонса, если есть
                preview_path = row["Картинка для анонса"]
                if preview_path:
                    if preview_path.startswith("http"):  # Проверяем, что это URL
                        photo_content = self.download_photo(preview_path)
                        if photo_content:
                            # Преобразуем bytes в ContentFile
                            product.preview_picture.save(os.path.basename(preview_path), ContentFile(photo_content))
                        else:
                            self.stdout.write(self.style.WARNING(f"Failed to download photo from {preview_path}"))
                    elif os.path.exists(preview_path):  # Если это локальный путь
                        with open(preview_path, "rb") as preview_file:
                            product.preview_picture.save(os.path.basename(preview_path), preview_file)
                    else:
                        self.stdout.write(self.style.WARNING(f"Photo file not found: {preview_path}"))

                product.save()
                self.stdout.write(self.style.SUCCESS(f"Imported product {external_code}"))

        self.stdout.write(self.style.SUCCESS("Finished importing products"))

    def download_photo(self, url):
        """Скачивает фото по URL и возвращает содержимое"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200 and "image" in response.headers.get("Content-Type", "").lower():
                return response.content
            else:
                self.stdout.write(self.style.WARNING(f"Invalid response for {url}: Status {response.status_code}, Content-Type {response.headers.get('Content-Type')}"))
                return None
        except requests.RequestException as e:
            self.stdout.write(self.style.WARNING(f"Error downloading {url}: {str(e)}"))
            return None
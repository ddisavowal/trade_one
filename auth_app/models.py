# from django.contrib.auth.models import AbstractUser
# from django.db import models

# class CustomUser(AbstractUser):
#     username = None  # Отключаем стандартное поле username
#     email = models.EmailField(unique=True)
#     otp_code = models.CharField(max_length=6, blank=True, null=True)
#     bitrix_id = models.CharField(max_length=20, blank=True, null=True)

#     USERNAME_FIELD = "email"  # Используем email вместо username
#     REQUIRED_FIELDS = []  # Оставляем пустым, иначе Django попросит username

#     def __str__(self):
#         return self.email
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

class CustomUserManager(BaseUserManager):
    """Менеджер пользователей, работающий без username"""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email обязателен")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Создание суперпользователя"""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    """Кастомная модель пользователя без username"""
    username = None  # Полностью убираем username
    email = models.EmailField(unique=True)
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    bitrix_id = models.CharField(max_length=20, blank=True, null=True)

    USERNAME_FIELD = "email"  # Вход по email
    REQUIRED_FIELDS = []  # Django не будет требовать username

    objects = CustomUserManager()  # Используем кастомный менеджер

    def __str__(self):
        return self.email

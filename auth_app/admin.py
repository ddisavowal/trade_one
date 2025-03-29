from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)  # Эта строка уже регистрирует модель
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "is_staff", "is_active")
    search_fields = ("email",)
    ordering = ("email",)

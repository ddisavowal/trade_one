
from django.contrib import admin
from django.urls import path
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('auth_app.urls')),
    path("api/", include("bitrix_api.urls")),
    path("api/", include("cdek_api.urls")),
]

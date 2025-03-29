
from django.urls import path
from .views import CDEKTrackingView
urlpatterns = [
    path("cdek/<str:tracking_number>/", CDEKTrackingView.as_view(), name="cdek-tracking"),
]

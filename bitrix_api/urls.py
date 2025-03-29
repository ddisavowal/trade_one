from django.urls import path

from bitrix_api.view_bonuses import AddBonusHistoryView, GetBitrixBonusHistoryView
from bitrix_api.views_orders import CreateBitrixOrderView, GetBitrixOrdersView, UpdateBitrixOrderView
from .views import  GetBitrixUserView,  UpdateBitrixUserView

urlpatterns = [
    path("bitrix-user/", GetBitrixUserView.as_view(), name="get_bitrix_user"),
    path("update-bitrix-user/", UpdateBitrixUserView.as_view(), name="update_bitrix_user"),
    
    path("bonus-history/", GetBitrixBonusHistoryView.as_view(), name="bonus-history"),
    path("update-bonus-history/", AddBonusHistoryView.as_view(), name="update-bonus-history"),
    
    path("create_order/", CreateBitrixOrderView.as_view(), name="create_order"),
    path("get_orders/", GetBitrixOrdersView.as_view(), name="get_orders"),
    path("update_order/", UpdateBitrixOrderView.as_view(), name="update_order"),
]

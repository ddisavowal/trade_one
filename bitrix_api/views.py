import json
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
import requests
from datetime import datetime

# BITRIX_WEBHOOK = "https://b24-q1x3hj.bitrix24.ru/rest/1/hh1tkmqd8bnz7rz2/"
BITRIX_WEBHOOK = settings.BITRIX_WEBHOOK

class GetBitrixUserView(APIView):
    """Получает данные пользователя из Битрикс24"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user  
        if not user.bitrix_id:
            return Response({"error": "У пользователя нет Bitrix ID"}, status=400)

        response = requests.get(
            BITRIX_WEBHOOK + "crm.contact.get",
            params={"id": user.bitrix_id}
        ).json()

        if "result" in response:
            return Response(response["result"], status=200)
        
        return Response({"error": "Ошибка получения данных"}, status=400)


class UpdateBitrixUserView(APIView):
    """Обновляет данные пользователя в Битрикс24"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.bitrix_id:
            return Response({"error": "У пользователя нет Bitrix ID"}, status=400)
        
        new_name = request.data.get("name")
        new_last_name = request.data.get("last_name")
        new_email = request.data.get("email")
        new_phone = request.data.get("phone")
        
        # Получаем текущие данные пользователя из Bitrix24
        response = requests.get(
            BITRIX_WEBHOOK + f"crm.contact.get?id={user.bitrix_id}"
        ).json()

        if "result" not in response:
            return Response({"error": "Ошибка получения данных из Bitrix24"}, status=400)

        current_data = response["result"]
        update_data = {"fields": {}}

    
        if new_name:
            update_data["fields"]["NAME"] = new_name
        if new_last_name:
            update_data["fields"]["LAST_NAME"] = new_last_name

        # Обновляем email
        if new_email:
            existing_emails = current_data.get("EMAIL", [])
            if existing_emails:
                existing_emails[0]["VALUE"] = new_email  # Заменяем первый email
            else:
                existing_emails.append({"VALUE": new_email, "VALUE_TYPE": "WORK"})  # Если нет, добавляем
            update_data["fields"]["EMAIL"] = existing_emails

        # Обновляем телефон
        if new_phone:
            existing_phones = current_data.get("PHONE", [])
            if existing_phones:
                existing_phones[0]["VALUE"] = new_phone  # Заменяем первый телефон
            else:
                existing_phones.append({"VALUE": new_phone, "VALUE_TYPE": "WORK"})  # Если нет, добавляем
            update_data["fields"]["PHONE"] = existing_phones

        

        response = requests.post(
            BITRIX_WEBHOOK + f"crm.contact.update?id={user.bitrix_id}",
            json=update_data
        ).json()

        if "result" in response and response["result"]:
            return Response({"message": "Данные успешно обновлены"}, status=200)

        return Response({"error": "Ошибка обновления данных"}, status=400)



# class GetBitrixBonusHistoryView(APIView):
#     """Получает историю бонусов пользователя из Битрикс24"""
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user  
#         if not user.bitrix_id:
#             return Response({"error": "У пользователя нет Bitrix ID"}, status=400)

#         response = requests.get(
#             BITRIX_WEBHOOK + "crm.contact.get",
#             params={"id": user.bitrix_id}
#         ).json()

#         if "result" in response:
#             try:
#                 # raw_history = response["result"].get("UF_CRM_1741346339", "[]")
#                 # print(raw_history)
#                 # history_list = json.loads(json.loads(f'"{raw_history}"')) 
#                 # print(history_list)
#                 raw_history = response["result"].get("UF_CRM_1741346339", "[]")
                
#                 # Проверяем, есть ли вообще данные
#                 if not raw_history:
#                     return Response({"bonus_history": []}, status=200)

#                 # Убираем лишние экранирования, если они есть
#                 cleaned_json = raw_history.replace('\\"', '"')  # Заменяем \" на "
                
#                 # Декодируем JSON
#                 history_list = json.loads(cleaned_json)
#                 # Двойное декодирование
#                 return Response({"bonus_history": history_list}, status=200)
#             except json.JSONDecodeError:
#                 return Response({"error": "Ошибка декодирования истории бонусов"}, status=400)
        
#         return Response({"error": "Ошибка получения данных"}, status=400)


# class AddBonusHistoryView(APIView):
#     """Добавляет запись в историю бонусов пользователя в Битрикс24"""
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         user = request.user  
#         if not user.bitrix_id:
#             return Response({"error": "У пользователя нет Bitrix ID"}, status=400)

#         # Получаем текущую историю бонусов
#         response = requests.get(
#             BITRIX_WEBHOOK + "crm.contact.get",
#             params={"id": user.bitrix_id}
#         ).json()

#         if "result" not in response:
#             return Response({"error": "Ошибка получения данных из Битрикс"}, status=400)

#         # Текущая история бонусов (если нет данных, то создаем пустой список)
#         raw_history = response["result"].get("UF_CRM_1741346339", "[]")
#         try:
#             history_list = json.loads(json.loads(f'"{raw_history}"'))
#         except json.JSONDecodeError:
#             history_list = []

#         # Получаем данные из запроса
#         new_entry = {
#             "date": request.data.get("date"),
#             "add": request.data.get("add", 0),
#             "off": request.data.get("off", 0)
#         }

#         # Добавляем новый элемент в список
#         history_list.append(new_entry)

#         # Кодируем обратно в JSON для Битрикса
#         updated_history = json.dumps(history_list, ensure_ascii=False)

#         # Отправляем обновленные данные в Битрикс24
#         update_response = requests.post(
#             BITRIX_WEBHOOK + f"crm.contact.update?id={user.bitrix_id}",
#             json={"fields": {"UF_CRM_1741346339": updated_history}}
#         ).json()

#         if "result" in update_response and update_response["result"]:
#             return Response({"message": "История бонусов обновлена", "new_entry": new_entry}, status=200)

#         return Response({"error": "Ошибка обновления данных в Битрикс"}, status=400)

#Заказы



# class CreateBitrixOrderView(APIView):
#     """Создаёт заказ в Битрикс24"""
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         user = request.user
#         if not user.bitrix_id:
#             return Response({"error": "У пользователя нет Bitrix ID"}, status=400)

#         order_title = request.data.get("title", "Новый заказ")
#         order_amount = request.data.get("amount", "0")  # Сумма заказа
#         order_description = request.data.get("description", "")

#         data = {
#             "fields": {
#                 "TITLE": order_title,
#                 "CONTACT_ID": user.bitrix_id,  # Привязываем к пользователю
#                 "STAGE_ID": "NEW",  # Этап заказа (можно менять)
#                 "OPPORTUNITY": order_amount,  # Сумма заказа
#                 "CURRENCY_ID": "RUB",  # Валюта
#                 "COMMENTS": order_description
#             }
#         }

#         response = requests.post(
#             BITRIX_WEBHOOK + "crm.deal.add",
#             json=data
#         ).json()

#         if "result" in response:
#             return Response({"order_id": response["result"], "message": "Заказ создан"}, status=201)

#         return Response({"error": "Ошибка при создании заказа"}, status=400)

# class GetBitrixOrdersView(APIView):
#     """Получает список заказов пользователя из Битрикс24"""
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user
#         if not user.bitrix_id:
#             return Response({"error": "У пользователя нет Bitrix ID"}, status=400)

#         response = requests.get(
#             BITRIX_WEBHOOK + "crm.deal.list",
#             params={
#                 "filter[CONTACT_ID]": user.bitrix_id,  # Фильтруем по ID пользователя
#                 "select[]": "ID",  # Получаем ID всех заказов
#                 "select[]": "TITLE",  # Название заказа
#                 "select[]": "STAGE_ID",  # Статус заказа
#                 "select[]": "OPPORTUNITY"  # Сумма заказа
#             }
#         ).json()

#         if "result" in response:
#             return Response(response["result"], status=200)

#         return Response({"error": "Ошибка получения заказов"}, status=400)

# class UpdateBitrixOrderView(APIView):
#     """Обновляет данные заказа в Битрикс24"""
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         user = request.user
#         order_id = request.data.get("order_id")
#         new_status = request.data.get("status")
#         new_amount = request.data.get("amount")

#         if not order_id:
#             return Response({"error": "Не указан ID заказа"}, status=400)

#         update_data = {"fields": {}}
#         if new_status:
#             update_data["fields"]["STAGE_ID"] = new_status
#         if new_amount:
#             update_data["fields"]["OPPORTUNITY"] = new_amount

#         response = requests.post(
#             BITRIX_WEBHOOK + f"crm.deal.update?id={order_id}",
#             json=update_data
#         ).json()

#         if "result" in response and response["result"]:
#             return Response({"message": "Заказ успешно обновлён"}, status=200)

#         return Response({"error": "Ошибка обновления заказа"}, status=400)

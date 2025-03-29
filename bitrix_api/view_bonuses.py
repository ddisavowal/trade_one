import json
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
import requests
from datetime import datetime

# BITRIX_WEBHOOK = "https://b24-q1x3hj.bitrix24.ru/rest/1/hh1tkmqd8bnz7rz2/"
BITRIX_WEBHOOK = settings.BITRIX_WEBHOOK

# Бонусы

class GetBitrixBonusHistoryView(APIView):
    """Получает историю бонусов пользователя из Битрикс24"""
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
            try:
                raw_history = response["result"].get("UF_CRM_BONUSES", "[]")
                
                # Проверяем, есть ли вообще данные
                if not raw_history or raw_history == "[]":
                    return Response({"bonus_history": []}, status=200)

                # Исправляем двойное экранирование (если есть)
                cleaned_json = raw_history.replace('\\"', '"')  
                
                # Декодируем JSON
                history_list = json.loads(cleaned_json)

                return Response({"bonus_history": history_list}, status=200)

            except json.JSONDecodeError:
                return Response({"error": "Ошибка декодирования истории бонусов"}, status=400)
        
        return Response({"error": "Ошибка получения данных"}, status=400)


class AddBonusHistoryView(APIView):
    """Добавляет запись в историю бонусов пользователя в Битрикс24"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user  
        if not user.bitrix_id:
            return Response({"error": "У пользователя нет Bitrix ID"}, status=400)

        # Получаем текущую историю бонусов
        response = requests.get(
            BITRIX_WEBHOOK + "crm.contact.get",
            params={"id": user.bitrix_id}
        ).json()

        if "result" not in response:
            return Response({"error": "Ошибка получения данных из Битрикс"}, status=400)

        # Текущая история бонусов (если нет данных, создаем пустой список)
        raw_history = response["result"].get("UF_CRM_BONUSES", "[]")
        try:
            if raw_history and raw_history != "[]":
                history_list = json.loads(raw_history.replace('\\"', '"'))  # Чистим экранирование
            else:
                history_list = []
        except json.JSONDecodeError:
            history_list = []

        # Получаем данные из запроса
        new_entry = {
            "date": request.data.get("date"),
            "add": request.data.get("add", 0),
            "off": request.data.get("off", 0)
        }

        # Добавляем новый элемент в список
        history_list.append(new_entry)

        # Кодируем обратно в JSON для Битрикса
        updated_history = json.dumps(history_list, ensure_ascii=False)

        # Отправляем обновленные данные в Битрикс24
        update_response = requests.post(
            BITRIX_WEBHOOK + f"crm.contact.update?id={user.bitrix_id}",
            json={"fields": {"UF_CRM_BONUSES": updated_history}}
        ).json()

        if "result" in update_response and update_response["result"]:
            return Response({"message": "История бонусов обновлена", "new_entry": new_entry}, status=200)

        return Response({"error": "Ошибка обновления данных в Битрикс"}, status=400)

    def get_loyalty_level(self, total_sum):
        if total_sum < 20000:
            return 1, "10% бонусов"
        elif total_sum < 35000:
            return 2, "15% бонусов"
        else:
            return 3, "20% бонусов"
        
    def update_bonus_history(self, user, add_bonus, off_bonus, order_amount):
        # Получаем текущую историю
        existing_data = json.loads(user.UF_CRM_BONUSES) if user.UF_CRM_BONUSES else {
            "total_sum": 0,
            "level": 1,
            "level_text": "10% бонусов",
            "count": 0,
            "history": []
        }
        
        # Обновляем сумму покупок
        existing_data["total_sum"] += order_amount
        
        # Обновляем баланс бонусов
        existing_data["count"] += add_bonus
        existing_data["count"] -= off_bonus
        
        # Уровень лояльности
        level, level_text = self.get_loyalty_level(existing_data["total_sum"])
        existing_data["level"] = level
        existing_data["level_text"] = level_text
        
        # Добавляем новую запись в историю
        existing_data["history"].append({
            "date": datetime.now().strftime('%d.%m.%Y'),
            "add": add_bonus,
            "off": off_bonus
        })
        
        # Ограничиваем длину истории (например, последние 50 операций)
        # existing_data["history"] = existing_data["history"][-50:]

        # Обновляем поле в профиле пользователя
        update_data = {
            "id": user.bitrix_id,
            "fields": {
                "UF_CRM_BONUSES": json.dumps(existing_data)
            }
        }
        response = requests.post(BITRIX_WEBHOOK + "crm.contact.update", json=update_data)
        
        if not response.json().get("result"):
            print(f"Ошибка обновления истории бонусов: {response.json()}")
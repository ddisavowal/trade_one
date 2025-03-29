import base64
import json
import re
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
import requests
from datetime import datetime

from bitrix_api.models import ProductPhoto

BITRIX_WEBHOOK = settings.BITRIX_WEBHOOK
BITRIX_DOMAIN = settings.BITRIX_DOMAIN

class CreateBitrixOrderView(APIView):
    """Создаёт заказ в Битрикс24 с товарами и скидками"""
    ### status
    ### NEW - Новая
    ### PREPARATION - Подготовка документов
    ### FINAL_INVOICE - Ожидание оплаты
    ### WON - Сделка завершена
    ### LOSE - Сделка провалена

    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.bitrix_id:
            return Response({"error": "У пользователя нет Bitrix ID"}, status=400)

        # Получаем данные из запроса
        deal_title = request.data.get('title', "Новый заказ")
        deal_date = request.data.get('deal_date')
        amount = float(request.data.get('amount'))
        # discount = request.data.get('discount', 0)
        currency = request.data.get('currency', 'RUB')
        status = request.data.get('status', 'NEW')
        products_list = request.data.get('products', [])
        use_bonus = float(request.data.get("use_bonus", 0))
        promo_code = float(request.data.get("promo_code", None))

        # Парсим товары
        products = self.parse_order_items(products_list)

        if not products:
            return Response({"error": "Не удалось распознать товары"}, status=400)

        bonus_discount, add_bonuses = self.create_bonuses(user, amount, use_bonus, promo_code)
        
        # Создание сделки
        deal_id = self.create_deal(
            title=deal_title,
            amount=amount,
            currency=currency,
            contact_id=user.bitrix_id,
            deal_date=deal_date,
            add_bonus= add_bonuses,
            off_bonus= bonus_discount
        )

        if deal_id:
            # Добавляем товары в сделку
            discount = bonus_discount if promo_code == 0 else promo_code
            self.add_products_to_deal(deal_id, products, discount)
            self.update_bonus_history(user, add_bonuses, bonus_discount, amount - discount)
            return Response({"order_id": deal_id, "message": "Заказ создан"}, status=201)

        return Response({"error": "Ошибка при создании заказа"}, status=400)

    def get_user_bonuses_from_bitrix(self, user_id):
        """Получает бонусы пользователя из Битрикс24 по ID"""
        url = f"{BITRIX_WEBHOOK}crm.contact.get"
        params = {"id": user_id}
        
        # Отправляем запрос к Битрикс24
        response = requests.get(url, params=params).json()

        # Если запрос успешный, возвращаем значение бонусов, иначе - пустую строку
        if response.get("result"):
            print(response["result"].get("UF_CRM_BONUSES", "{}"))
            return response["result"].get("UF_CRM_BONUSES", "{}")  # Возвращаем бонусы, если они есть
        return "{}"  # если нет, возвращаем пустую строку


    def create_bonuses(self, user, order_amount, use_bonus, promo_code):
        # Получаем текущие бонусы и историю
        # existing_data = json.loads(self.get_user_bonuses_from_bitrix(user.bitrix_id)) if user.bitrix_id else {
        #     "count": 0
        # }
        bonuses_json = self.get_user_bonuses_from_bitrix(user.bitrix_id)
    
        try:
            existing_data = json.loads(bonuses_json)  # Пробуем декодировать строку
        except json.JSONDecodeError:
            # Если произошла ошибка при декодировании, создаем пустой объект
            existing_data = {"count": 0}
        available_bonus = existing_data.get("count", 0)

        # Если указан промокод — бонусы не начисляем
        add_bonus = 0
        off_bonus = 0

        if promo_code:
            use_bonus = 0
        else:
            # Списываем бонусы (если разрешено)
            if use_bonus > 0:
                max_bonus = min(order_amount * 0.5, available_bonus)
                off_bonus = min(use_bonus, max_bonus)
                

            # Начисляем бонусы (если не использовался промокод)
            if off_bonus == 0:
                level, _ = self.get_loyalty_level(existing_data.get("total_sum", 0))
                if level == 1:
                    add_bonus = order_amount * 0.1
                elif level == 2:
                    add_bonus = order_amount * 0.15
                elif level == 3:
                    add_bonus = order_amount * 0.2
                    
        return off_bonus, add_bonus
                    
    def get_loyalty_level(self, total_sum):
        if total_sum < 20000:
            return 1, "10% бонусов"
        elif total_sum < 35000:
            return 2, "15% бонусов"
        else:
            return 3, "20% бонусов"
        

    def update_bonus_history(self, user, add_bonus, off_bonus, order_amount):
        # Получаем текущую историю
        bonuses_json = self.get_user_bonuses_from_bitrix(user.bitrix_id)
    
        try:
            existing_data = json.loads(bonuses_json)  # Пробуем декодировать строку
        except json.JSONDecodeError:
            # Если произошла ошибка при декодировании, создаем пустой объект
            existing_data = {"total_sum": 0,
            "level": 1,
            "level_text": "10% бонусов",
            "count": 0,
            "history": []
            }
        # existing_data = json.loads(self.get_user_bonuses_from_bitrix(user.bitrix_id)) if user.bitrix_id else {
        #     "total_sum": 0,
        #     "level": 1,
        #     "level_text": "10% бонусов",
        #     "count": 0,
        #     "history": []
        # }
        
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

    def create_deal(self, title, amount, currency, contact_id, deal_date, add_bonus, off_bonus):
        """Создание сделки в Битрикс24"""
        deal_url = f"{BITRIX_WEBHOOK}/crm.deal.add"
        
        # Конвертируем дату в нужный формат
        if deal_date:
            try:
                deal_date = datetime.strptime(deal_date, '%Y-%m-%d %H:%M:%S').isoformat()
            except ValueError:
                deal_date = None
        
        deal_data = {
            "fields": {
                "TITLE": title,
                "OPPORTUNITY": amount,
                "CURRENCY_ID": currency,
                "CLOSEDATE": deal_date,
                "CONTACT_ID": contact_id,
                "UF_CRM_BONUS_ADD": add_bonus,
                "UF_CRM_BONUS_OFF": off_bonus
                
            }
        }
       
        response = requests.post(deal_url, json=deal_data).json()
        if response.get('result'):
            return response['result']
        return None

    def parse_order_items(self, products):
        """
        Разбирает строку товаров.
        Возвращает список словарей: [{'NAME': '...', 'QUANTITY': ..., 'PRICE': ...}]
        """
        items = []
        for product in products:
            # match = re.search(r"(.*?)\s*(?:\((\d+)\))?\s*x\s*(\d+)\s*≡\s*(\d+)", priduct)
            # if match:
            xml = product['xml']
            # crm_sku = match.group(2) if match.group(2) else None
            quantity = product['count']
            price = float(product['price'])
            
            items.append({
                "XML_ID": xml,
                "QUANTITY": quantity,
                "PRICE": price
            })
        return items

    def find_product_id(self, product):
        """Ищет товар в Битрикс24 по XML_ID и возвращает его ID."""
        url = BITRIX_WEBHOOK + "crm.product.list"
        
        # Поиск по XML_ID 
        params = {"filter[XML_ID]": product['XML_ID'], "select": ["ID"]}
        response = requests.get(url, params=params).json()
        if response.get('result'):
            return response['result'][0]['ID']
        
        return None

    def add_products_to_deal(self, deal_id, products, discount):
        """Добавляет товары в сделку в Битрикс24 с учётом скидки."""
        product_rows = []
        try:
            discount = float(discount) if discount else 0
        except ValueError:
            discount = 0
        
        total_price = sum(product["PRICE"] for product in products)
        discount_rate = round((discount / total_price) * 100, 2) if total_price > 0 else 0
        
        for product in products:
            product_id = self.find_product_id(product)
            quantity = product["QUANTITY"]
            price_per_unit = product["PRICE"]/quantity
            
            discounted_price = round(price_per_unit * (1 - discount_rate / 100), 2)

            if product_id:
                product_rows.append({
                    "PRODUCT_ID": product_id,
                    "PRICE": discounted_price,
                    "QUANTITY": quantity,
                    "DISCOUNT_TYPE_ID": 2,
                    "DISCOUNT_RATE": discount_rate
                })

        if product_rows:
            response = requests.post(BITRIX_WEBHOOK + "crm.deal.productrows.set", json={
                "id": deal_id,
                "rows": product_rows
            }).json()

            if response.get('result'):
                print(f"Товары добавлены в сделку {deal_id}")
            else:
                print(f"Ошибка добавления товаров: {response.get('error_description')}")

class GetBitrixOrdersView(APIView):
    """Получает список заказов пользователя из Битрикс24 с детальной информацией"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.bitrix_id:
            return Response({"error": "У пользователя нет Bitrix ID"}, status=400)

        # Получаем список сделок пользователя
        response = requests.get(
            BITRIX_WEBHOOK + "crm.deal.list",
            params={
                "filter[CONTACT_ID]": user.bitrix_id,
                "select[]": "ID",  
                "select[]": "TITLE",  
                "select[]": "STAGE_ID",  
                "select[]": "OPPORTUNITY",  
                "select[]": "CLOSEDATE",
                "select[]": "DATE_MODIFY",
                "select[]": "CLOSED",
                "select[]": "UF_CRM_BONUS_ADD",
                "select[]": "UF_CRM_BONUS_OFF",
                "select[]": "UF_CRM_CDEK_NUMBER",
            }
        ).json()
        
        print(response["result"])
        
        
        if (response["result"] == []):
            return Response([], status=200)

        if not response.get("result"):
            return Response({"error": "Ошибка получения заказов"}, status=400)

        deals = response["result"]
        detailed_deals = []

        for deal in deals:
            deal_id = deal["ID"]

            # Получаем полную информацию по каждой сделке
            deal_data = requests.get(
                BITRIX_WEBHOOK + f"crm.deal.get",
                params={"id": deal_id}
            ).json().get("result", {})

            # Получаем товары в сделке
            products_response = requests.get(
                BITRIX_WEBHOOK + f"crm.deal.productrows.get",
                params={"id": deal_id}
            ).json()

            products = products_response.get("result", [])
            product_details = []

            # Обрабатываем каждый продукт
            for product in products:
                product_id = product.get("PRODUCT_ID")
                photo_url = self.get_product_photo(product_id)  # Получаем URL фото

                product_details.append({
                    "product_id": product_id,
                    "name": product.get("PRODUCT_NAME"),
                    "quantity": product.get("QUANTITY"),
                    "price": product.get("PRICE"),
                    "discount_rate": product.get("DISCOUNT_RATE"),
                    "photo_url": photo_url  # Добавляем URL фото
                })

            # Собираем детальную информацию по сделке
            detailed_deals.append({
                "id": deal_id,
                "title": deal_data.get("TITLE"),
                "status": self.get_status(deal_data.get("STAGE_ID")),
                "amount": deal_data.get("OPPORTUNITY"),
                "closed": deal_data.get("CLOSED"),
                "modifydate": self.format_date(deal_data.get("DATE_MODIFY")),
                "closedate": self.format_date(deal_data.get("CLOSEDATE")),
                "discount": deal_data.get("DISCOUNT_SUM"),  # Скидка, если есть
                "add_bonus": deal_data.get("UF_CRM_BONUS_ADD"),
                "off_bonus": deal_data.get("UF_CRM_BONUS_OFF"),
                "cdek_number": deal_data.get("UF_CRM_CDEK_NUMBER"),
                "products": product_details,
            })

        return Response(detailed_deals, status=200)
    
    def get_status(self, status):
        if status == "NEW":
            return "Создан"
        if status == "PREPARATION":
            return "Подготовка"
        if status == "FINAL_INVOICE":
            return "Ожидание отправки"
        if status == "WON":
            return "Завершен"
        if status == "LOSE":
            return "Отменен"
        ### NEW - Новая
        ### PREPARATION - Подготовка документов
        ### FINAL_INVOICE - Ожидание оплаты
        ### WON - Сделка завершена
        ### LOSE - Сделка провалена
    def format_date(self, iso_date):
        if not iso_date:
            return "Дата не указана"
        # Парсим ISO-строку в объект datetime
        date_obj = datetime.fromisoformat(iso_date)
        # Форматируем в dd.MM.YYYY
        return date_obj.strftime("%d.%m.%Y")
    def get_product_photo(self, product_id):
        """Получает содержимое фото продукта как base64 из Django по external_code"""
        if not product_id:
            print(f"Ошибка: product_id отсутствует")
            return None

        # Шаг 1: Получаем XML_ID (внешний код) продукта из Bitrix24
        product_response = requests.get(
            BITRIX_WEBHOOK + f"crm.product.get",
            params={"id": product_id}
        ).json()

        product_data = product_response.get("result", {})
        external_code = product_data.get("XML_ID")
        if not external_code:
            print(f"Ошибка: XML_ID отсутствует для product_id {product_id}")
            return None

        # Шаг 2: Ищем фото в базе Django по external_code
        try:
            product_photo = ProductPhoto.objects.get(external_code=external_code)
            if not product_photo.preview_picture:
                print(f"Ошибка: Фото отсутствует для external_code {external_code}")
                return None

            with open(product_photo.preview_picture.path, "rb") as photo_file:
                photo_content = photo_file.read()
                return f"data:image/jpeg;base64,{base64.b64encode(photo_content).decode('utf-8')}"
        except ProductPhoto.DoesNotExist:
            print(f"Ошибка: Продукт с external_code {external_code} не найден в базе Django")
            return None
        

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
#                 "filter[CONTACT_ID]": user.bitrix_id,
#                 "select[]": "ID",
#                 "select[]": "TITLE",
#                 "select[]": "STAGE_ID",
#                 "select[]": "OPPORTUNITY",
#                 "select[]": "CLOSEDATE"  
#             }
#         ).json()

#         if response.get("result"):
#             return Response(response["result"], status=200)

#         return Response({"error": "Ошибка получения заказов"}, status=400)


class UpdateBitrixOrderView(APIView):
    """Обновляет данные заказа в Битрикс24"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        order_id = request.data.get("order_id")
        new_status = request.data.get("status")
        new_amount = request.data.get("amount")
        cdek_number = request.data.get("cdek_number")

        if not order_id:
            return Response({"error": "Не указан ID заказа"}, status=400)

        update_data = {"fields": {}}
        if new_status:
            update_data["fields"]["STAGE_ID"] = new_status
        if new_amount:
            update_data["fields"]["OPPORTUNITY"] = new_amount
        if cdek_number:
            update_data["fields"]["UF_CRM_CDEK_NUMBER"] = cdek_number

        response = requests.post(
            BITRIX_WEBHOOK + f"crm.deal.update?id={order_id}",
            json=update_data
        ).json()

        if response.get("result"):
            return Response({"message": "Заказ успешно обновлён"}, status=200)

        return Response({"error": "Ошибка обновления заказа"}, status=400)

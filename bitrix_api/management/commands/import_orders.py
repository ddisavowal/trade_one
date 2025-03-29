import csv
from datetime import datetime
import json
import os
import re
import requests
from django.core.management.base import BaseCommand
from django.conf import settings

# Настройки Битрикс24
BITRIX_WEBHOOK = settings.BITRIX_WEBHOOK
CSV_FILE_PATH = os.path.join(settings.BASE_DIR, 'bitrix_api', 'import', 'orders.csv')

class Command(BaseCommand):
    help = "Импортирует заказы из CSV в Битрикс24"

    # def add_arguments(self, parser):
    #     parser.add_argument('csv_file', type=str, help="../../import/orders.csv")

    # def handle(self, *args, **options):
    def handle(self,  **options):
        csv_file_path = CSV_FILE_PATH
        # options['csv_file']

        try:
            # delete_all_deals()
            with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)

                for row in reader:
                    print()
                    contact_email = row.get('Рабочий e-mail')
                    deal_title = row.get('Товары в заказе')
                    deal_date = row.get('Дата оплаты')
                    amount = row.get('Сумма заказа')
                    discount = row.get('Скидка')
                    
                    currency = row.get('Валюта', 'RUB')

                    # Получаем ID контакта в Битрикс24
                    contact_id = self.get_contact_id(contact_email)
                    if not contact_id:
                        self.stdout.write(self.style.ERROR(f"Контакт {contact_email} не найден!"))
                        continue  # Пропускаем, если контакта нет
                    
                    # Парсим товары
                    products = self.parse_order_items(deal_title)
                    
                    product_names = ", ".join([product["NAME"] for product in products])
                    
                    add_bonuses = self.create_bonuses(contact_id, amount, discount)
                    
                    # Создаём сделку
                    deal_id = self.create_deal(
                        title=product_names, 
                        amount=amount, 
                        currency=currency, 
                        contact_id=contact_id, 
                        deal_date=deal_date, 
                        add_bonus=add_bonuses
                    )
                    # # Добавляем товары
                    if deal_id:
                        discount = float(discount) if discount else 0
                        self.add_products_to_deal(deal_id, products, discount)
                        self.update_bonus_history(contact_id, add_bonuses, float(amount) - discount)
                        # self.update_deal_total(deal_id, amount, discount)
            
            self.stdout.write(self.style.SUCCESS("Импорт завершён!"))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка импорта: {e}"))

    def get_contact_id(self, email): 
        """Получаем ID контакта по email"""
        search_url = BITRIX_WEBHOOK + "crm.contact.list"
        params = {
            "filter": {},
            "select": ["ID", "EMAIL"]
        }

        response = requests.get(search_url, params=params)
        data = response.json()

        if not data.get('result'):
            return None

        for contact in data['result']:
            emails = contact.get("EMAIL", [])
            for email_info in emails:
                if email_info.get("VALUE") == email:
                    return contact["ID"]

        return None
    
    def get_user_bonuses_from_bitrix(self, user_id):
        """Получает бонусы пользователя из Битрикс24 по ID"""
        url = f"{BITRIX_WEBHOOK}crm.contact.get"
        params = {"id": user_id}
        
        # Отправляем запрос к Битрикс24
        response = requests.get(url, params=params).json()

        # Если запрос успешный, возвращаем значение бонусов, иначе - пустую строку
        if response.get("result"):
            bonuses_json = response["result"].get("UF_CRM_BONUSES") or "{}"
            return bonuses_json
        return "{}"  # если нет, возвращаем пустую строку


    def create_bonuses(self, user_id, order_amount, promo_code):
       
        bonuses_json = self.get_user_bonuses_from_bitrix(user_id)
    
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
        if (existing_data == {}):
            existing_data = {"total_sum": 0,
            "level": 1,
            "level_text": "10% бонусов",
            "count": 0,
            "history": []
            }
        # available_bonus = existing_data.get("count", 0)

        # Если указан промокод — бонусы не начисляем
        add_bonus = 0
        if promo_code:
            add_bonus = 0
        else:
            # Начисляем бонусы (если не использовался промокод)
            level, _ = self.get_loyalty_level(existing_data.get("total_sum", 0))
            order_amount = float(order_amount)
            if level == 1:
                add_bonus = round(order_amount * 0.1)
            elif level == 2:
                add_bonus = round(order_amount * 0.15)
            elif level == 3:
                add_bonus = round(order_amount * 0.2)
                    
        return add_bonus
                    
    def get_loyalty_level(self, total_sum):
        if total_sum < 20000:
            return 1, "10% бонусов"
        elif total_sum < 35000:
            return 2, "15% бонусов"
        else:
            return 3, "20% бонусов"
        

    def update_bonus_history(self, bitrix_id, add_bonus, order_amount):
        # Получаем текущую историю
        bonuses_json = self.get_user_bonuses_from_bitrix(bitrix_id)
    
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
        if (existing_data == {}):
            existing_data = {"total_sum": 0,
            "level": 1,
            "level_text": "10% бонусов",
            "count": 0,
            "history": []
            }
        
        
        add_bonus = float(add_bonus) 
       
        # Обновляем сумму покупок
        existing_data["total_sum"] += order_amount
        
        # Обновляем баланс бонусов
        existing_data["count"] += add_bonus
        
        # Уровень лояльности
        level, level_text = self.get_loyalty_level(existing_data["total_sum"])
        existing_data["level"] = level
        existing_data["level_text"] = level_text
        
        # Добавляем новую запись в историю
        existing_data["history"].append({
            "date": datetime.now().strftime('%d.%m.%Y'),
            "add": add_bonus,
            "off": 0
        })
        
        print(existing_data)
        

        # Обновляем поле в профиле пользователя
        update_data = {
            "id": bitrix_id,
            "fields": {
                "UF_CRM_BONUSES": json.dumps(existing_data)
            }
        }
        response = requests.post(BITRIX_WEBHOOK + "crm.contact.update", json=update_data)
        
        
        
        if response.json().get("result"):
            self.stdout.write(self.style.SUCCESS(f"Бонусы обновлены"))
        else:
            self.stdout.write(self.style.ERROR(f"Ошибка обновления истории бонусов: {response.json()}"))
        
    
    def create_deal(self, title, amount, currency, contact_id, deal_date, add_bonus):
        """Создаём сделку в Битрикс24"""
        deal_url = f"{BITRIX_WEBHOOK}/crm.deal.add"
        
        if deal_date:
            try:
                deal_date = datetime.strptime(deal_date, '%Y-%m-%d %H:%M:%S').isoformat()
            except ValueError:
                deal_date = None
        
        deal_data = {
            "fields": {
                "TITLE": title,
                "OPPORTUNITY": amount,
                # "DISCOUNT_SUM": discount,
                # "DISCOUNT_TYPE_ID":1,
                "CURRENCY_ID": currency,
                "CLOSEDATE" : deal_date,
                "CONTACT_ID": contact_id,
                "UF_CRM_BONUS_ADD": add_bonus,
                "UF_CRM_BONUS_OFF": 0
            }
        }
       
        response = requests.post(deal_url, json=deal_data)
        result = response.json()
        
        if result.get('result'):
            deal_id = result['result']
            self.stdout.write(self.style.SUCCESS(f"Сделка '{title}' успешно создана!"))
            return deal_id
        else:
            self.stdout.write(self.style.ERROR(f"Ошибка создания сделки: {result}"))
            return None
    
    def parse_order_items(self, order_str):
        """
        Разбирает строку товаров из CSV.
        Возвращает список словарей: [{'NAME': '...', 'QUANTITY': ..., 'PRICE': ...}]
        """
        items = []
        for line in order_str.split("\n"):  # Разбиваем по строкам
            match = re.search(r"(.*?)\s*(?:\((\d+)\))?\s*x\s*(\d+)\s*≡\s*(\d+)", line)
            if match:
                name = match.group(1).strip().upper()  # Основное название
                crm_sku = match.group(2) if match.group(2) else None  # CRM_SKU (если есть)
                quantity = int(match.group(3))  # Количество
                price = float(match.group(4))  # Цена
                
                # print("ЗАКАЗ")
                # print(name)
                # print(crm_sku)
                # print('\n')
                
               
                items.append({
                    "NAME": name,
                    "CRM_SKU": crm_sku,
                    "QUANTITY": quantity,
                    "PRICE": price
                })
        return items
    
    def find_product_id(self, product_name, crm_sku=None):
        """Ищет товар в Битрикс24 по названию и возвращает его ID."""
        url = BITRIX_WEBHOOK + "crm.product.list"
        
        # print(crm_sku)
        # print('\n')
        
        if crm_sku:
            # PROPERTY_CRM_SKU
            # params_test = {"filter": {}, "select": ["ID", "NAME", "XML_ID", "UF_*"]}
            # response = requests.get(url, params=params_test).json()
            # print(response['result'][0])
            crm_sku_clean = crm_sku.strip()
            params = {"filter[CODE]": crm_sku_clean, "select": ["ID"]}
            response = requests.get(url, params=params).json()
            if response.get('result'):
                # print(crm_sku_clean)
                # print(product_name)
                # print(response['result'][0]['ID'])
                return response['result'][0]['ID']
            # else:
            #     print(response)
        print(product_name)
        params = {
            "filter[NAME]": product_name,
            "select": ["ID"]
        }
        response = requests.get(url, params=params).json()
        
        if response.get('result'):
            return response['result'][0]['ID']
        else:
            print(response)
        return None

    def add_products_to_deal(self, deal_id, products, discount):
        """Добавляет товары в сделку в Битрикс24."""
        product_rows = []
        try:
            discount = float(discount) if discount else 0  # Приводим скидку к float
        except ValueError:
            discount = 0
        total_price = sum(product["PRICE"] for product in products)
       
        discount_rate = round((discount / total_price) * 100, 2) if total_price > 0 else 0
       
        for product in products:
            product_id = self.find_product_id(product["NAME"], product["CRM_SKU"])
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
            requests.post(BITRIX_WEBHOOK + "crm.deal.productrows.set", json={
                "id": deal_id,
                "rows": product_rows
            })
            self.stdout.write(self.style.SUCCESS(f"Товары добавлены в сделку {deal_id}"))
        else:
            self.stdout.write(self.style.ERROR(f"Не найдено товаров для добавления в сделку"))
       

    def update_deal_total(self, deal_id, total_sum, discount):
        """Обновляем сумму сделки в Битрикс24 с учётом общей скидки."""
        deal_update_data = {
            "id": deal_id,
            "fields": {
                "OPPORTUNITY": total_sum,         # Сумма сделки с учётом скидки
                "DISCOUNT_SUM": discount,         # Общая сумма скидки
                "DISCOUNT_TYPE_ID": 1             # Тип скидки = фиксированная сумма
            }
        }
        
        response = requests.post(BITRIX_WEBHOOK + 'crm.deal.update', json=deal_update_data)
        if response.json().get('result'):
            print(f"Сумма сделки {deal_id} обновлена до {total_sum} с учётом скидки {discount}")
        else:
            print(f"Ошибка обновления суммы сделки: {response.json()}")


def delete_all_deals():
    url_list = f"{BITRIX_WEBHOOK}/crm.deal.list"
    url_delete = f"{BITRIX_WEBHOOK}/crm.deal.delete"
    
    # Получаем все сделки
    params = {
        "select": ["ID"],
        "filter": {}
    }
    response = requests.get(url_list, json=params).json()
    
    if not response.get('result'):
        print("Нет сделок для удаления.")
        return
    
    deals = response['result']
    
    for deal in deals:
        deal_id = deal['ID']
        delete_response = requests.post(url_delete, json={"id": deal_id}).json()
        if delete_response.get('result'):
            print(f"Сделка {deal_id} удалена успешно!")
        else:
            print(f"Ошибка удаления сделки {deal_id}: {delete_response.get('error_description')}")

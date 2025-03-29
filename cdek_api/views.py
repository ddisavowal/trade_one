import requests
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

# Данные для API СДЭК
CDEK_CLIENT_ID = "ps6qL9pwwZQ5bXzCKmtbyqpSCUAL9TuZ"
CDEK_CLIENT_SECRET = "jpTrLjaJef5lyNZ2vgRcWFOu5NjdKg2Y"
# CDEK_CLIENT_ID = "wqGwiQx0gg8mLtiEKsUinjVSICCjtTEP"
# CDEK_CLIENT_SECRET = "RmAmgvSgSl1yirlz9QupbzOJVqhCxcP5"

# curl -X POST "https://api.edu.cdek.ru/v2/oauth/token" \
#      -H "Content-Type: application/x-www-form-urlencoded" \
#      -d "grant_type=client_credentials&client_id=wqGwiQx0gg8mLtiEKsUinjVSICCjtTEP&client_secret=RmAmgvSgSl1yirlz9QupbzOJVqhCxcP5"

# curl -X POST "https://api.edu.cdek.ru/v2/orders" \
#      -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzY29wZSI6WyJsb2NhdGlvbjphbGwiLCJvcmRlcjphbGwiLCJwYXltZW50OmFsbCJdLCJleHAiOjE3NDEyNzc2MzUsImF1dGhvcml0aWVzIjpbInNoYXJkLWlkOnJ1LTAxIiwiY2xpZW50LWNpdHk60J3QvtCy0L7RgdC40LHQuNGA0YHQuiwg0J3QvtCy0L7RgdC40LHQuNGA0YHQutCw0Y8g0L7QsdC70LDRgdGC0YwiLCJhY2NvdW50LWxhbmc6cnVzIiwiY29udHJhY3Q60JjQnC3QoNCkLdCT0JvQky0yMiIsImFwaS12ZXJzaW9uOjEuMSIsImFjY291bnQtdXVpZDplOTI1YmQwZi0wNWE2LTRjNTYtYjczNy00Yjk5YzE0ZjY2OWEiLCJjbGllbnQtaWQtZWM1OmVkNzVlY2Y0LTMwZWQtNDE1My1hZmU5LWViODBiYjUxMmYyMiIsImNvbnRyYWN0LWlkOmRlNDJjYjcxLTZjOGMtNGNmNS04MjIyLWNmYjY2MDQ0ZThkZiIsImNsaWVudC1pZC1lYzQ6MTQzNDgyMzEiLCJzb2xpZC1hZGRyZXNzOmZhbHNlIiwiY29udHJhZ2VudC11dWlkOmVkNzVlY2Y0LTMwZWQtNDE1My1hZmU5LWViODBiYjUxMmYyMiIsImZ1bGwtbmFtZTrQotC10YHRgtC40YDQvtCy0LDQvdC40LUg0JjQvdGC0LXQs9GA0LDRhtC40Lgg0JjQnCJdLCJqdGkiOiJzNDVtWExYRlZBd1VrZGhpUGdQVUhZcGtuRmciLCJjbGllbnRfaWQiOiJ3cUd3aVF4MGdnOG1MdGlFS3NVaW5qVlNJQ0NqdFRFUCJ9.cTEhdJhK_AQ4wowrHMmTAZAJZQia2wQ4EHY4RYn2NqCH__9ZyojTOOEToAVgAnYCA8SKn5ehm2VXC6DZf1dWQOHdbNsuFjNThCz9_VzXZ3fS-lYRDntOXFmMLsXk8P9HBcAnAemDXBNgc06Y9NYEfA2ZE6Kf6XBx5Vbl4AfKURHpMJ2ayA-BTP-xe9UaukfI-NcH8X8cvTiymAlOxtGjOPqbs_L4UHLMpmZ8mpFbTcnnou4Rq5vIKxTmdpitoo4zc_I72Iv59deQHB1Bd5YgXMiZoIVWqAX5Hg5Kvo0VwKOlbxu3igy1fZj8-WKreC1PMdyQJJFH-GdghLNXyIQL9w" \
#      -H "Content-Type: application/json" \
#      -d '{
#            "number": "test_order_123", 
#            "tariff_code": 136, 
#            "sender": { "company": "Test", "name": "John Doe", "phone": "+79998887766" }, 
#            "recipient": { "company": "Test", "name": "Jane Smith", "phone": "+79991234567" },
#            "services": [],
#            "packages": [
#              { "number": "package_123", "weight": 1000, "length": 10, "width": 10, "height": 10 }
#            ]
#          }'

class CDEKTrackingView(APIView):
    """ Получение статуса посылки через API СДЭК """
    permission_classes = [AllowAny]

    def get(self, request, tracking_number):
        # Получаем токен API СДЭК
        auth_response = requests.post(
            "https://api.cdek.ru/v2/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CDEK_CLIENT_ID,
                "client_secret": CDEK_CLIENT_SECRET
            },
            verify=False
        ).json()
        
        if "access_token" not in auth_response:
            return Response({"error": "Ошибка авторизации в СДЭК"}, status=400)

        access_token = auth_response["access_token"]

        # Делаем запрос к API СДЭК для получения статуса посылки
        response = requests.get(
            f"https://api.cdek.ru/v2/orders?cdek_number={tracking_number}",
            headers={"Authorization": f"Bearer {access_token}"},
        verify=False
        ).json()

        if "requests" not in response:
            return Response({"error": "Посылка не найдена"}, status=404)

        order_data = response  # Берём первую посылку
        
        # status = order_data.get("statuses", [{"description": "Статус неизвестен"}])[-1]
        status = []
        for stat in order_data['entity']['statuses']:
            status.append({'name' : stat['name'], 'date': stat['date_time']})
        # date = order_data['entity']['statuses'][0]['date_time']
        fromLocation = order_data['entity']['from_location']['city']
        toLocation = order_data['entity']['to_location']['city']
        
        # 

        return Response({
            "tracking_number": tracking_number,
            'from': fromLocation,
            'to': toLocation,
            "status": status,
            # "date": date,
            
        }, status=200)

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.contrib.auth import get_user_model
import requests
# from .serializers import LoginSerializer, RegisterSerializer
from django.core.mail import send_mail
import random
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from auth_app.serializers import LoginSerializer

User = get_user_model()

BITRIX_WEBHOOK = settings.BITRIX_WEBHOOK

class RegisterView(APIView):
    """Запрашивает код подтверждения email"""
    permission_classes = [AllowAny]
    def post(self, request):
        email = request.data.get("email")
        
        if not email:
            return Response({"error": "Введите email"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Проверка, существует ли пользователь с таким email в базе Django
        if User.objects.filter(email=email).exists():
            bitrix_response = requests.get(
                BITRIX_WEBHOOK + "crm.contact.list",
                params={"filter[EMAIL]": email}
            ).json()
            if bitrix_response.get("result"):
                print(email)
            else:
                return Response({"error": "Пользователь с таким email уже зарегистрирован"}, status=status.HTTP_400_BAD_REQUEST)

        otp_code = str(random.randint(100000, 999999))

        # Сохраняем код в БД (но не создаём полноценного пользователя)
        user, created = User.objects.get_or_create(email=email)
        user.otp_code = otp_code
        user.set_password("")  # Очищаем пароль, пока не подтвердит email
        user.save()

        # Отправляем код на email
        send_mail(
            "Код подтверждения",
            f"Ваш код подтверждения: {otp_code}",
            "ddisavowal@yandex.ru",  # Отправитель
            [email],  # Получатель
            fail_silently=False,
        )

        return Response({"message": "Код отправлен на email"}, status=status.HTTP_200_OK)

class VerifyOTPView(APIView):
    """Подтверждает email и завершает регистрацию"""
    permission_classes = [AllowAny]
    def post(self, request):
        email = request.data.get("email")
        otp_code = request.data.get("otp_code")
        password = request.data.get("password")
        name = request.data.get("name")

        if not all([email, otp_code, password]):
            return Response({"error": "Заполните все поля"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email, otp_code=otp_code)

            # Устанавливаем пароль и активируем пользователя
            user.set_password(password)
            user.otp_code = None
            user.save()
            
            # Проверяем, существует ли контакт в Битрикс с таким email
            bitrix_response = requests.get(
                BITRIX_WEBHOOK + "crm.contact.list",
                params={"filter[EMAIL]": email}
            ).json()

            if bitrix_response.get("result"):
                print(email)
                # Если контакт существует в Битрикс, привязываем существующий Bitrix ID к пользователю
                user.bitrix_id = bitrix_response["result"][0]["ID"]
                user.save()
            else:
                # Если контакт не найден в Битрикс, создаём новый контакт
                bitrix_response = requests.post(
                    BITRIX_WEBHOOK + "crm.contact.add",
                    json={
                        "fields": {
                            "NAME": name,
                            "EMAIL": [{"VALUE": email, "VALUE_TYPE": "WORK"}]
                        }
                    }
                ).json()

                if "result" in bitrix_response:
                    user.bitrix_id = bitrix_response["result"]
                    user.save()

            return Response({"message": "Email подтверждён, регистрация завершена"}, status=status.HTTP_201_CREATED)

        except User.DoesNotExist:
            return Response({"error": "Неверный код"}, status=status.HTTP_400_BAD_REQUEST)


            # # Добавляем пользователя в Битрикс24
            # bitrix_response = requests.post(
            #     BITRIX_WEBHOOK + "crm.contact.add",
            #     json={"fields": {"NAME":name, "EMAIL": [{"VALUE": user.email, "VALUE_TYPE": "WORK"}]}}
            # ).json()

            # if "result" in bitrix_response:
            #     user.bitrix_id = bitrix_response["result"]
            #     user.save()

        #     return Response({"message": "Email подтверждён, регистрация завершена"}, status=status.HTTP_201_CREATED)

        # except User.DoesNotExist:
        #     return Response({"error": "Неверный код"}, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    """Авторизация пользователя"""
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    """API для выхода (отзывает refresh-токен)"""
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"error": "Refresh-токен отсутствует"}, status=status.HTTP_400_BAD_REQUEST)
            
            token = RefreshToken(refresh_token)
            token.blacklist()  # Делаем refresh-токен недействительным
            
            return Response({"message": "Выход выполнен успешно"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
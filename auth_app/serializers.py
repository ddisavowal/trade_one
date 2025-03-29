from rest_framework import serializers
from django.contrib.auth import get_user_model
import random
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        otp_code = str(random.randint(100000, 999999))
        user = User.objects.create(email=validated_data['email'], otp_code=otp_code)
        user.set_password(validated_data['password'])
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = User.objects.filter(email=data["email"]).first()
        if user and user.check_password(data["password"]):
            refresh = RefreshToken.for_user(user)
            return {"access": str(refresh.access_token), "refresh": str(refresh)}
        raise serializers.ValidationError("Ошибка авторизации")
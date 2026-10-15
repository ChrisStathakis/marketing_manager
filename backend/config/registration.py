"""Public user registration (AllowAny, disabled unless settings.ALLOW_REGISTRATION).

Returns a JWT pair on success so the new user is signed in immediately.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if get_user_model().objects.filter(username=value).exists():
            raise serializers.ValidationError("username already taken.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        return get_user_model().objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not settings.ALLOW_REGISTRATION:
            return Response(
                {"detail": "Registration is disabled. Set DJANGO_ALLOW_REGISTRATION=True to enable it."},
                status=status.HTTP_403_FORBIDDEN,
            )
        ser = RegisterSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        user = ser.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {"username": user.username, "refresh": str(refresh), "access": str(refresh.access_token)},
            status=status.HTTP_201_CREATED,
        )

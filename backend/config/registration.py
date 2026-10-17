"""Public user registration.

Registration is open while the instance has no accounts yet, so the first
person to sign up can set up the admin. Once a user exists it closes and only
reopens when ``settings.ALLOW_REGISTRATION`` is explicitly enabled — after
that, accounts are created by the admin (Django admin).

The first account is made a superuser/staff so it can manage integrations and
the Django admin. Returns a JWT pair on success so the new user is signed in
immediately.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


def users_exist() -> bool:
    """Whether any account has been created yet."""
    return User.objects.exists()


def registration_open() -> bool:
    """Open to everyone until the first account exists, then opt-in only."""
    return settings.ALLOW_REGISTRATION or not users_exist()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("username already taken.")
        return value

    def create(self, validated_data):
        # The very first account is the admin; later ones are regular users.
        if not User.objects.exists():
            return User.objects.create_superuser(
                username=validated_data["username"],
                email="",
                password=validated_data["password"],
            )
        return User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not registration_open():
            return Response(
                {"detail": "Registration is closed. Ask an admin to create your account."},
                status=status.HTTP_403_FORBIDDEN,
            )
        ser = RegisterSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        user = ser.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "username": user.username,
                "is_admin": user.is_superuser,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_201_CREATED,
        )

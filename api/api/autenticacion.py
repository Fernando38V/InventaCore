from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class TokenConVencimiento(TokenAuthentication):
    """TokenAuthentication cuyo token vence a las TOKEN_VIGENCIA_HORAS (24)."""

    def authenticate_credentials(self, key):
        usuario, token = super().authenticate_credentials(key)
        horas = getattr(settings, 'TOKEN_VIGENCIA_HORAS', 24)
        if timezone.now() - token.created > timedelta(hours=horas):
            token.delete()
            raise AuthenticationFailed('La sesión venció. Inicie sesión de nuevo.')
        return usuario, token

import jwt
from django.conf import settings
from rest_framework import authentication
from rest_framework import exceptions
from .models import User

class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        token = None
        
        if auth_header:
            try:
                prefix, token = auth_header.split(' ')
                if prefix.lower() != 'bearer':
                    token = None
            except ValueError:
                token = None
        
        # Fallback to cookie if not in header
        if not token:
            token = request.COOKIES.get('access_token')
            
        if not token:
            return None
            
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.DecodeError:
            return None
            
        user_id = payload.get('user_id')
        if not user_id:
            return None
            
        try:
            # Fetch the actual user from the database so roles and permissions work
            user = User.objects.select_related('role').get(id=user_id)
        except User.DoesNotExist:
            return None
        
        # Ensure the user is active
        if not user.is_active:
            raise exceptions.AuthenticationFailed('User account is disabled')
            
        return (user, token)

    def authenticate_header(self, request):
        return 'Bearer'

from drf_spectacular.extensions import OpenApiAuthenticationExtension

class JWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'users.authentication.JWTAuthentication'
    name = 'BearerAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
            'description': 'Enter your JWT access token in the format: Bearer <token>'
        }


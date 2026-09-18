import jwt
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
        if user_id:
            return User.objects.get(id=user_id, is_active=True)
    except (jwt.PyJWTError, User.DoesNotExist):
        pass
    return AnonymousUser()

class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        if not token:
            headers = dict(scope.get('headers', []))
            if b'authorization' in headers:
                auth_header = headers[b'authorization'].decode('utf-8')
                if auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
            elif b'cookie' in headers:
                cookies = headers[b'cookie'].decode('utf-8')
                for cookie in cookies.split(';'):
                    cookie = cookie.strip()
                    if cookie.startswith('access_token='):
                        token = cookie.split('=', 1)[1]
                        break

        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()

        return await self.inner(scope, receive, send)

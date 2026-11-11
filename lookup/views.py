from rest_framework import viewsets
from drf_spectacular.utils import extend_schema
from users.permissions import IsAdminOrReadOnly
from .models import Lookup
from .serializers import LookupSerializer

@extend_schema(tags=['Lookup'])
class LookupViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = Lookup.objects.all()
    serializer_class = LookupSerializer
    permission_classes = [IsAdminOrReadOnly]

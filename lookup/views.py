from rest_framework import viewsets
<<<<<<< HEAD
=======
from users.permissions import IsAdminOrReadOnly
>>>>>>> d3f86bdf3dac8fc402d56ff1ebace7e1271c6a92
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
<<<<<<< HEAD
=======
    pagination_class = None
>>>>>>> d3f86bdf3dac8fc402d56ff1ebace7e1271c6a92

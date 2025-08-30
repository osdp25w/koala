from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from utils.renderers import KoalaRenderer


class BaseAPIView(APIView):
    renderer_classes = [KoalaRenderer]


class BaseGenericViewSet(GenericViewSet):
    renderer_classes = [KoalaRenderer]

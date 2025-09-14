from django.urls import path

from bike.websocket.consumers import BikeErrorLogNotificationConsumer

# WebSocket URL patterns
websocket_urlpatterns = [
    path('ws/bike/error-logs/', BikeErrorLogNotificationConsumer.as_asgi()),
]

from django.urls import path

from bike.websocket.consumers import (
    BikeErrorLogNotificationConsumer,
    BikeRealtimeStatusConsumer,
)

# WebSocket URL patterns
websocket_urlpatterns = [
    path('ws/bike/error-logs/', BikeErrorLogNotificationConsumer.as_asgi()),
    path('ws/bike/realtime-status/', BikeRealtimeStatusConsumer.as_asgi()),
]

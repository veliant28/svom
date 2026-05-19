from django.urls import re_path

from .consumers import CommerceUserConsumer

websocket_urlpatterns = [
    re_path(r"^ws/commerce/user/$", CommerceUserConsumer.as_asgi()),
]


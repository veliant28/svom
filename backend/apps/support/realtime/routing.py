from django.urls import re_path

from .consumers import SupportQueueConsumer, SupportThreadConsumer, SupportUserConsumer, SupportWallboardConsumer

websocket_urlpatterns = [
    re_path(r"^ws/support/user/$", SupportUserConsumer.as_asgi()),
    re_path(r"^ws/support/queue/$", SupportQueueConsumer.as_asgi()),
    re_path(r"^ws/support/wallboard/$", SupportWallboardConsumer.as_asgi()),
    re_path(r"^ws/support/threads/(?P<thread_id>[0-9a-f\-]+)/$", SupportThreadConsumer.as_asgi()),
]

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from django_redis import get_redis_connection
from .tasks import save_message_to_db

redis_conn = get_redis_connection("default")  # Use Django Redis connection

@api_view(["POST"])
def push_command(request, sn):
    payload = request.data
    group_name = f"device_{sn}"
    channel_layer = get_channel_layer()
    message = json.dumps({"sn": sn, **payload})

    # Check if device sn is active in Redis set
    is_active = redis_conn.sismember("active_devices", sn)
    if not active:
        redis_conn.rpush(f"queue:{sn}", message)
        return Response({"status": "queued"})
    
    group_sender = async_to_sync(channel_layer.group_send)
    group_sender(group_name, {"type": "send_command", "message": message})
    return Response({"status": "sent"})

def _schema_from_sn(sn):
    return "public" if "_" not in sn else sn.split("_", 1)[0]

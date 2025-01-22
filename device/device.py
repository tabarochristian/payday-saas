from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from datetime import datetime
import logging
import httpx
import json
import os

# Load environment variables
load_dotenv()

# Configuration
# WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:8000/api/v1/hook/device/")

# FastAPI App Initialization
app = FastAPI()

# Logger Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WebSocketApp")

# Tracks connected devices by serial number (sn)
connected_clients = {}
host_connected_clients = {}

# Helper Functions
def send_to_webhook(webhook: str, data: dict):
    """
    Celery task to send data to a webhook. Retries on failure.

    :param self: Reference to the Celery task instance
    :param data: The data to send to the webhook
    """
    
    if not data:
        logger.warning("No data to send to webhook.")
        return

    headers = {"Content-Type": "application/json"}
    response = httpx.post(webhook, json=data, headers=headers)
    logger.info(f"Webhook success: {response.status_code}")
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(f"Webhook error: {e}")


async def forward_command_to_device(sn: str, data: dict):
    """
    Forwards a command to a connected WebSocket device.

    :param sn: Serial number of the target device
    :param command: Command data to send
    :raises HTTPException: If the device is not connected
    """
    print(data)
    if sn in connected_clients:
        websocket = connected_clients[sn]
        await websocket.send_text(json.dumps(data))
        logger.info(f"Command sent to {sn}")
    else:
        logger.warning(f"Device {sn} not connected.")
        raise HTTPException(status_code=404, detail=f"Device {sn} not connected.")

async def handle_message_from_device(websocket: WebSocket, webhook:str, sn: str, message: str):
    """
    Processes messages received from a WebSocket device.

    :param sn: Serial number of the device
    :param message: JSON-formatted message string
    """
    try:
        data = json.loads(message)
        websocket.send_text(json.dumps({
            "result": True,
            "ret": data.get("cmd"),
            "cloudtime": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        }))
        send_to_webhook(webhook, data)
        logger.info(f"Message received from {sn}: {data}")
    except json.JSONDecodeError:
        logger.warning(f"Invalid JSON received from {sn}: {message}")


# HTTP Endpoints
@app.post("/send-command")
async def send_command(request: Request):
    """
    Accepts a command via HTTP and forwards it to a WebSocket device.

    :param request: HTTP request containing command data
    :return: JSON response indicating success or failure
    """
    data = await request.json()
    sn = data.get("sn")
    cmd = data.get("cmd")

    if not sn or not cmd:
        raise HTTPException(status_code=400, detail="Missing 'sn' or 'cmd' in request.")

    try:
        await forward_command_to_device(sn, data)
        return JSONResponse(content={"status": "success", "message": "Command sent"})
    except Exception as e:
        logger.error(f"Error sending command: {e}")
        raise HTTPException(status_code=500, detail=f"Error sending command: {str(e)}")

def host_name(websocket: WebSocket):
    host = websocket.headers.get("host").split(":")[0]
    host = host.split('.')
    host.remove('device')
    host = '.'.join(host)
    return host

def url_from_host_name(host_name):
    return f"http://{host_name}/employee/device"

# WebSocket Endpoint
@app.websocket("/pub/chat")
async def websocket_endpoint(websocket: WebSocket):
    """
    Handles WebSocket connections from devices.

    :param websocket: The WebSocket connection object
    """
    logger.info("WebSocket connection initiated.")
    webhook = url_from_host_name(host_name(websocket))
    logger.info(f"Webhook URL: {webhook}")
    await websocket.accept()

    try:
        # Perform handshake: Device sends a registration message
        register_message = await websocket.receive_text()
        register_data = json.loads(register_message)

        if register_data.get("cmd") != "reg" or "sn" not in register_data:
            logger.warning("Invalid handshake message.")
            await websocket.close(code=4000, reason="Invalid handshake message")
            return

        sn = register_data["sn"]
        connected_clients[sn] = websocket
        logger.info(f"Device {sn} registered.")

        # if host not in host_connected_clients:
        #    host_connected_clients[host] = []
        # host_connected_clients[host].append(sn)

        # Acknowledge registration
        response = {
            "ret": "reg",
            "result": True,
            "nosenduser": True,
            "cloudtime": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        }
        await websocket.send_text(json.dumps(response))
        send_to_webhook(webhook, register_data)

        # Handle incoming messages
        while True:
            try:
                message = await websocket.receive_text()
                await handle_message_from_device(websocket, webhook, sn, message)
            except WebSocketDisconnect:
                send_to_webhook(webhook, {"cmd": "disconnected", "sn": sn})
                logger.info(f"Device {sn} disconnected.")
                connected_clients.pop(sn, None)
                break
            except Exception as e:
                logger.error(f"Error handling message from {sn}: {e}")
                send_to_webhook(webhook, {"cmd": "disconnected", "sn": sn})
                break
    except Exception as e:
        send_to_webhook(webhook, {"cmd": "disconnected", "sn": sn})
        logger.error(f"WebSocket connection error: {e}")
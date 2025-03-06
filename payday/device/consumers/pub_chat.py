import json
import logging
from datetime import datetime
from channels.generic.websocket import WebsocketConsumer

logger = logging.getLogger(__name__)

class PubChat(WebsocketConsumer):
    """
    WebSocket consumer to handle chat connections from devices.
    """
    sn = None

    def connect(self):
        logger.info("WebSocket connection initiated.")
        self.accept()

    def disconnect(self, close_code):
        sn = getattr(self, 'sn', None)
        logger.info(f"Device {sn} disconnected.")

    def receive(self, text_data):
        try:
            # Perform handshake: Device sends a registration message
            register_data = json.loads(text_data)

            if not hasattr(self, 'registered'):
                if register_data.get("cmd") != "reg" or "sn" not in register_data:
                    logger.warning("Invalid handshake message.")
                    self.close(code=4000, reason="Invalid handshake message")
                    return

                self.sn = register_data["sn"]
                self.registered = True
                logger.info(f"Device {self.sn} registered.")

                # Acknowledge registration
                response = {
                    "ret": "reg",
                    "result": True,
                    "nosenduser": True,
                    "cloudtime": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                }
                self.send(text_data=json.dumps(response))
            else:
                # Handle incoming messages
                data = json.loads(text_data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            self.close(code=4001, reason="Invalid JSON message")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            self.close()

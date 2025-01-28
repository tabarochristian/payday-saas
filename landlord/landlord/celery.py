from celery import Celery
import os
import ssl

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'landlord.settings')

REDIS_URL_WITH_SSL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
REDIS_BACKEND_USE_SSL_CONFIG = {'ssl_cert_reqs': ssl.CERT_NONE}
BROKER_USE_SSL_CONFIG = {'ssl_cert_reqs': ssl.CERT_NONE}

def is_redis_url_with_ssl(redis_url):
    return redis_url.startswith('rediss://')

app = Celery("landlord")

if is_redis_url_with_ssl(REDIS_URL_WITH_SSL):
    app.conf.update(
        broker_use_ssl=BROKER_USE_SSL_CONFIG,
        redis_backend_use_ssl=REDIS_BACKEND_USE_SSL_CONFIG,
        broker_connection_retry_on_startup=True
    )

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

if __name__ == '__main__':
    app.start()

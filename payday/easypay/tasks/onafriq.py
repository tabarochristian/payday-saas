from celery import shared_task
import requests
from payroll.models import PaidEmployee
from django.conf import settings


@shared_task
def send_mobile_payment(payload):
    try:
        print('on y est ............................................')
        print("Envoi de la requête de paiement à Onafriq avec les données:", payload)
        # headers = {
        #     "Authorization": f"Token {settings.ONAFRIQ_TOKEN}",
        #     "Content-Type": "application/json"
        # }
        # response = requests.post(
        #     "https://api.onafriq.com/api/v5/payments", json=payload, headers=headers, timeout=10)
        # response.raise_for_status()
        # # Tu peux enregistrer ici une confirmation ou log
        # print("Paiement réussi:", payload['full_name'])
        # return {"status": "success", "response": response.json()}
    except requests.RequestException as e:
        return {"status": "error", "error": str(e)}

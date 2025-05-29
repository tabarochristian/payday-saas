import requests
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models.functions import Concat
from django.db import models
from easypay.models import Mobile
from payroll.models import PaidEmployee
from payday import settings


@receiver(post_save, sender=Mobile)
def mobile_payment_order_created(sender, instance, created, **kwargs):
    if not created:
        return

    employees = PaidEmployee.objects.filter(
        payment_method='MOBILE MONEY',
        payroll=instance.payroll,
    ).exclude(
        mobile_number__isnull=True
    ).annotate(
        full_name=Concat('last_name', models.Value(
            ' '), 'middle_name',  output_field=models.CharField()),
    ).values(
        'mobile_number',
        'full_name',
        'net',
        'id'
    )

    for employee in employees:
        payload = {
            "phonenumber": str(employee["mobile_number"]),
            "first_name": employee["full_name"].split()[0],
            "last_name": employee["full_name"].split()[0],
            "account": "2956481",
            "currency": "CDF",
            "amount": float(employee['net']),
            "request_currency": "CDF",
            "description": "Payout in CDF",
            "payment_type": "money",
            "metadata": {
                "employee_id": employee["id"],
                "payroll_id": instance.id,
                "payroll_name": str(instance.payroll),
            }
        }

        try:
            headers = {
                "Authorization": f"Token {settings.ONAFRIQ_TOKEN}",
                "Content-Type": "application/json"
            }
            response = requests.post(
                "https://api.onafriq.com/api/v5/payments", json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            print("Paiement réussi pour", employee["full_name"])
            print("Détails du paiement:", response.json())
        except requests.RequestException as e:
            print("Erreur lors du paiement de",
                  employee["full_name"], ":", str(e))

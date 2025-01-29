from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from payroll.models import Payroll, PaidEmployee
from payroll.tasks import Payer

from employee.models import Employee

@receiver(pre_save, sender=Payroll)
def payroll_create(sender, instance, **kwargs):
    if 'errors' in instance._metadata: return
    instance._metadata['errors'] = []

@receiver(post_save, sender=Payroll)
def payroll_created(sender, instance, created, **kwargs):
    if not created: return
    
    # start process of creating payroll employee
    
    # Payer().run(instance.id)
    #Payer().delay(instance.id)

def duplicate(payroll):
    fields = [f.name for f in Employee._meta.get_fields()]
    employees = Employee.objects.all().values(*fields)

    paid_employees = [PaidEmployee(**employee, attendances=0, payroll=payroll) for employee in employees]
    PaidEmployee.objects.bulk_create(paid_employees)

    # apply attendance
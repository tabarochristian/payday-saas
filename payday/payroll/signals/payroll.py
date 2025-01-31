from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from payroll.models import Payroll, PaidEmployee
from payroll.tasks import Payer

from employee.models import Employee, Attendance
import pandas as pd

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

    def get_field_name(name):
        return name.split('__')[0]

    fields = [f"{f.name}__name" if f.is_relation else f.name for f in Employee._meta.get_fields()]
    employees = Employee.objects.all().values(*fields)

    df = pd.from_records(list(employees))
    df.columns = [get_field_name(c) for c in df.columns]
    df['attendance'] = 0

    # fetch all attendance of the period of the payroll
    attendances = Attendance.objects.filter(date__range=(payroll.start_date, payroll.end_date))
    attendances = attendances.values('employee__registration_number', 'checked_at__date').annotate(attendances_count=Count('employee__name'))

    paid_employees = [PaidEmployee(**employee, attendances=0, payroll=payroll) for employee in employees]
    PaidEmployee.objects.bulk_create(paid_employees)

    # apply attendance
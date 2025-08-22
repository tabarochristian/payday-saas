from payroll.utils import PayrollProcessor
from payroll.models import *

instance = Payroll.objects.get(id=16)
PaidEmployee.objects.filter(payroll=instance).delete()

PayrollProcessor(instance, "public").process()
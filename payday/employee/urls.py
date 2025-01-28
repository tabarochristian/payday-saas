from django.urls import path
from employee.views import *

app_name = 'employee'

urlpatterns = [
    path('print/<str:pk>', EmployeePrint.as_view(), name='print'),
    path('change/<str:pk>', Employee.as_view(), name='change'),
    path('device', DeviceAPIView.as_view(), name='device'),    
]

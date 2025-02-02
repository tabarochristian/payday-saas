from django.urls import path
from payroll.views import *

app_name = 'payroll'

urlpatterns = [
    path('synthesis/<str:func>/<int:pk>', Synthesis.as_view(), name='synthesis'),

    path('listing/<int:pk>', Listing.as_view(), name='listing'),
    path('canvas/<str:actor>', Canvas.as_view(), name='canvas'),

    path('payslips/<str:pk>', Payslips.as_view(), name='payslips'),
    path('preview/<str:pk>', Preview.as_view(), name='preview'),
    path('payslip/<int:pk>', Payslip.as_view(), name='payslip'),
    path('slips', Slips.as_view(), name='slips'),
]

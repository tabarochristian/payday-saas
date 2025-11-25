from .views import ApiViewSet
from django.urls import path
from .views import *
app_name = 'api'


urlpatterns = [
    path('autocomplete/<str:app>/<str:model>/<str:to_field>',
         Autocomplete.as_view(), name='autocomplete'),

    path('v1/<str:app>/<str:model>', ApiViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='list'),

    path('v1/<str:app>/<str:model>/<str:pk>', ApiViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='detail'),

    path('v1/aggregate/<str:function>/<str:app>/<str:model>/<str:field>', 
        Aggregate.as_view(), 
        name="aggregate"
    ),

    path('v1/annotate/<str:function>/<str:app>/<str:model>/<str:field>', 
        Annotate.as_view(), 
        name="annotate"
    ),

    path('sync/rollapp/employee', EmployeeSyncWithRollApp.as_view(),
         name='employee-sync-api'),

    path('session', SetSessionView.as_view(), name='set-session')
]

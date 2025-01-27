from django.template.loader import render_to_string
from celery import shared_task
from core import utils

from django.contrib.contenttypes.models import ContentType
from core.models import Menu
from django.apps import apps

@shared_task(name='daily')
def new_tenant(schema, user):
    utils.set_schema(schema)

    apps = ContentType.objects.filter(app_label__in=['employee', 'payroll']).values_list('app_label', flat=True).distinct()
    excluded_models = ['children','itempaid','paidemployee','advancesalary','specialemployeeitem']
    
    for app_label in apps:
        obj, created = Menu.objects.get_or_create(**{
            'name': app_label,
            'created_by_id': user
        })
        if not created: return obj
        qs = ContentType.objects\
            .filter(app_label=app_label)\
                .exclude(model__in=excluded_models)
        obj.children.set(qs)
        print(f'Created menu for {app_label}')

    return "Success"
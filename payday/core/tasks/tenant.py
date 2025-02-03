from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from django.core.management import call_command
from django.conf import settings
from celery import shared_task
from django.apps import apps
from core import utils

from core.models import Menu

@shared_task(name='new_tenant')
def new_tenant(schema, user):
    try:
        utils.set_schema(schema)
    except Exception as e:
        logger.error(e)

    exclude = ['document', 'child', 'education', 'advancesalarypayment', 'itempaid', 'paidemployee', 'specialemployeeitem']
    apps = ContentType.objects.exclude(
        app_label__in=['contenttypes', 'sessions', 'admin', 'auth', 'core']
    ).values_list('app_label', flat=True).distinct()
    
    for app in apps:
        obj, created = Menu.objects.get_or_create(**{
            'name': app,
            'created_by_id': user
        })
        if not created: return obj
        qs = ContentType.objects.filter(app_label=app)\
            .exclude(model__in=exclude)
        obj.children.set(qs)
        print(f'Created menu and sub-menu for {app}')

    # check if fixtures exists in fixtures folder
    # load fixtures

    call_command('loaddata', 'fixtures/core.json')
    call_command('loaddata', 'fixtures/employee.json')
    call_command('loaddata', 'fixtures/payroll.json')

    return "Success"
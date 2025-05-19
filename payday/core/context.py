from django.utils.translation import gettext as _
from core.models import Menu, ActionRequired
from django.urls import reverse_lazy
from django.apps import apps

TARGET_APPS = ["employee", "payroll", "leave"]
EXCLUDED_MODELS = {"child", "device", "document", "education", 
"itempaid", "paidemployee", "specialemployeeitem", "advancesalarypayment"}

def base(request):
    if not request.user.is_authenticated: return {}

    apps_models = {
        app: [model for model in app.get_models() if model._meta.model_name not in EXCLUDED_MODELS]
        for app in apps.get_app_configs() if app.label in TARGET_APPS
    }
    
    menu = [{
        'class': 'active',
        'href': f'#{app.label}',
        'title': app.verbose_name,
        # 'icon': f'bi-{getattr(app, "icon", "default-icon")}',  # Ensure safe reference
        'children': [
            {
                'title': model._meta.verbose_name,
                'permission': f'{app.label}.view_{model._meta.model_name}',
                'href': reverse_lazy('core:list', kwargs={'app': app.label, 'model': model._meta.model_name})
            }
            for model in apps_models[app] if request.user.has_perm(f'{app.label}.view_{model._meta.model_name}')
        ]
    }
    for app in apps_models.keys()]
    
    menu.insert(0, dict({
        'title': _('Tableau de bord'),
        'href': reverse_lazy('core:home'),
        'icon': 'bi-grid-fill',
        'forced': True,
        'description': _('Tous vos widgets en un seul endroit, des statistiques, des graphiques et bien plus encore.')
    }))

    menu.insert(1, dict({
        'title': _('Action requise'),
        'href': reverse_lazy('core:action-required'),
        'icon': 'bi-lightning-fill',
        'forced': True,
        'badge': ActionRequired.objects.count(),
        'description': _('Les actions qui nécessitent votre attention.')
    }))

    menu.insert(2, dict({
        'title': _('Notifications'),
        'href': reverse_lazy('core:notifications'),
        'icon': 'bi-bell',
        'forced': True,
        'badge': request.user.notifications.unread().count(),
        'description': _('Les notifications qui vous sont destinées.')
    }))
    
    menu.insert(len(menu), dict({
        'class': 'active',
        'title': _('Paramètres'),
        'href': '#',
        'icon': 'bi-gear-fill',
        'description': _('Paramètres de votre organisation.'),
        'children': [item for item in [
        #{
        #    'title': _('Menus'),
        #    'href': reverse_lazy('core:list', kwargs={'app': 'core', 'model': 'menu'}),
        #    'permission': 'core.view_menu',
        #    'description': _('Faite la disposition de vos menus.')
        #}, 
        {
            'title': _('Importeur'),
            'href': reverse_lazy('core:list', kwargs={'app': 'core', 'model': 'importer'}),
            'permission': 'core.view_menu',
            'description': _('Importez vos données en masse.')
        }, 
        {
            'title': _('Modèle de document'),
            'href': reverse_lazy('core:list', kwargs={'app': 'core', 'model': 'template'}),
            'permission': 'core.view_template',
            'description': _('Créez des modèles de document reutilisable pour vos models.')
        }, {
            'title': _('Widget'),
            'href': reverse_lazy('core:list', kwargs={'app': 'core', 'model': 'widget'}),
            'permission': 'core.view_widget',
            'description': _('Créez des widgets pour votre tableau de bord, ainsi que listing.')
        }, 
        #{
        #    'title': _('Préférences'),
        #    'href': reverse_lazy('core:list', kwargs={'app': 'core', 'model': 'preference'}),
        #    'permission': 'core.view_preference',
        #    'description': _('Définissez vos préférences pour une meilleure expérience.')
        #}, 
        {
            'title': _('Utilisateurs'),
            'href': reverse_lazy('core:list', kwargs={'app': 'core', 'model': 'user'}),
            'permission': 'core.view_user',
            'description': _('Gérez les utilisateurs de votre organisation.')
        }, {
            'title': _('Roles'),
            'href': reverse_lazy('core:list', kwargs={'app': 'core', 'model': 'group'}),
            'permission': 'auth.view_group',
            'description': _('Gérez les roles de votre organisation.')
        }, {
            'title': _('Terminaux'),
            'href': reverse_lazy('core:list', kwargs={'app': 'device', 'model': 'device'}),
            'description': _('Gérez vos terminaux de presence'),
            'permission': 'device.view_device',
        }, 
        #{
        #    'title': _('Job'),
        #    'href': reverse_lazy('core:list', kwargs={'app': 'core', 'model': 'job'}),
        #    'permission': 'core.view_job',
        #    'description': _('Mettez en place des tâches automatisées.')
        #}, 
        {
            'title': _('Journal d\'activité'),
            'href': reverse_lazy('core:activity-log'),
            'permission': 'admin.view_logentry',
            'description': _('Consultez l\'historique des activités.')
        }] if request.user.is_superuser or request.user.is_staff] # if request.user.has_perm(item.get('permission'))]
    }))
    
    menu.append(dict({
        'class': 'active',
        'title': _('Profil'),
        'href': '#',
        'icon': 'bi-person-lines-fill',
        'children': [{
            'title': _('Modifier le mot de passe'),
            'href': reverse_lazy('core:password-change'),
            'description': _('Changer votre mot de passe.')
        }, {
            'title': _('Se déconnecter'),
            'href': reverse_lazy('core:logout'),
            'description': _('Déconnectez-vous de votre compte.')
        }]
    }))
    return {'menus': menu}

def notifications(request):
    if not request.user.is_authenticated: return {}
    notifications = Notification.objects.filter(**{
        '_to': request.user,
        'viewed': False
    }).count()
    return {'count': notifications}

def action_required(request):
    data = {'count': 0}
    from employee.models import Device
    is_devices = Device.objects.all().exists()
    if not is_devices: 
        data['count'] += 1
    return data

"""
from django.db.models import Case, When, Value, CharField, Sum
from django.shortcuts import render
from .models import Payroll
from django.utils import timezone

def get_payroll_data(request):
    payroll_data = Payroll.objects.annotate(
        month=Case(
            When(start_dt__month=1, then=Value('January')),
            When(start_dt__month=2, then=Value('February')),
            When(start_dt__month=3, then=Value('March')),
            When(start_dt__month=4, then=Value('April')),
            When(start_dt__month=5, then=Value('May')),
            When(start_dt__month=6, then=Value('June')),
            When(start_dt__month=7, then=Value('July')),
            When(start_dt__month=8, then=Value('August')),
            When(start_dt__month=9, then=Value('September')),
            When(start_dt__month=10, then=Value('October')),
            When(start_dt__month=11, then=Value('November')),
            When(start_dt__month=12, then=Value('December')),
            output_field=CharField(),
        )
    ).values('month').annotate(
        total_amount=Sum('amount')
    ).values('month', 'total_amount')

    # Convert to a format that can be used by the frontend chart
    payroll_data = list(payroll_data)

    context = {
        'payroll_data': payroll_data
    }
    return render(request, 'payroll_chart.html', context)

"""
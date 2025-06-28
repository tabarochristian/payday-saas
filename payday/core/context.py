from django.utils.translation import gettext as _
from notifications.models import Notification
from core.models import ActionRequired
from django.urls import reverse_lazy
from django.apps import apps

TARGET_APPS = ["employee", "payroll", "leave"]
EXCLUDED_MODELS = ("child", "device", "document", "education", 
                   "itempaid", "paidemployee", "specialemployeeitem", "advancesalarypayment")

def base(request):
    if not request.user.is_authenticated:
        return {}

    # Get models from allowed apps, excluding certain models
    apps_models = {
        app: [model for model in app.get_models() if model._meta.model_name not in EXCLUDED_MODELS]
        for app in apps.get_app_configs() if app.label in TARGET_APPS
    }

    # Construct menu dynamically
    menu = [
        {
            "class": "active",
            "href": f"#{app.label}",
            "title": app.verbose_name,
            "children": [
                {
                    "title": model._meta.verbose_name,
                    "permission": f"{app.label}.view_{model._meta.model_name}",
                    "href": reverse_lazy("core:list", kwargs={"app": app.label, "model": model._meta.model_name}),
                }
                for model in apps_models.get(app, []) if request.user.has_perm(f"{app.label}.view_{model._meta.model_name}")
            ],
        }
        for app in apps_models.keys()
    ]
    
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
            'title': _('Sous-organisation'),
            'href': reverse_lazy('core:list', kwargs={'app': 'core', 'model': 'suborganization'}),
            'description': _('Cree une sous-organisation'),
            'permission': 'core.view_suborganization',
        },
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
        {
            'title': _('Préférences'),
            'href': reverse_lazy('core:list', kwargs={'app': 'core', 'model': 'preference'}),
            'permission': 'core.view_preference',
            'description': _('Définissez vos préférences pour une meilleure expérience.')
        }, 
        {
            'title': _('Utilisateurs'),
            'href': reverse_lazy('core:list', kwargs={'app': 'core', 'model': 'user'}),
            'permission': 'core.view_user',
            'description': _('Gérez les utilisateurs de votre organisation.')
        }, {
            'title': _('Roles'),
            'href': reverse_lazy('core:list', kwargs={'app': 'core', 'model': 'group'}),
            'permission': 'core.view_group',
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
            'title': _('Flux d’approbation'),
            'permission': 'core.view_workflow',
            'description': _('Étapes de validation'),
            'href': reverse_lazy('core:list', kwargs={'app':'core', 'model':'workflow'}),
        },
        {
            'title': _('Approbation'),
            'description': _('Approval'),
            'permission': 'core.view_approval',
            'href': reverse_lazy('core:list', kwargs={'app':'core', 'model':'approval'}),
        },
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
    count_notifications = Notification.objects.unread()\
        .filter(recipient=request.user).count()
    return {'count': count_notifications}

def action_required(request):
    data = {'count': 0}
    from employee.models import Device
    is_devices = Device.objects.all().exists()
    if not is_devices: 
        data['count'] += 1
    return data
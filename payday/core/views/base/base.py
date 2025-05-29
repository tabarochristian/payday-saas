from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.utils.translation import gettext as _
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.conf import settings
from django.views import View
from django.apps import apps

from core.views.mixins import FielderMixin, LoggerMixin, DocumentMixin  # Import your custom mixins


class BaseView(LoginRequiredMixin, PermissionRequiredMixin, FielderMixin, LoggerMixin, DocumentMixin, View):
    """
    Base view providing common functionality such as permission checking,
    queryset building, model retrieval, logging, and keyword generation.
    """
    actions = []                      # List of allowed actions, e.g. ["add", "delete", "view"]
    template_name = None              # Default template name (can be overridden)
    DEBUG = settings.DEBUG

    def get_actions(self):
        """
        Return the allowed actions.
        """
        return self.actions

    def get_action_buttons(self):
        """
        Return a list of action buttons. This method may be overridden
        in child classes.
        """
        return []

    def get_template_name(self):
        """
        Return the template to be used by the view. If the model defines a
        'list_template' attribute, that is returned; otherwise, the default
        template_name is used.
        """
        model_class = self.get_model()
        return getattr(model_class, 'list_template', self.template_name)

    def get_queryset(self):
        """
        Return a queryset of objects filtered based on the current user's
        row-level security. This method uses the user's `get_user_rls`
        method to build the filter kwargs.
        """
        model_class = self.get_model()
        user_rls = self.request.user.get_user_rls(
            app=model_class._meta.app_label,
            model=model_class._meta.model_name
        )
        if hasattr(model_class.objects, 'for_user'):
            return model_class.objects.for_user(user=self.request.user)
        return model_class.objects.filter(**user_rls)

    def get_permission_required(self):
        """
        Build a list of required permission strings for the actions defined on
        this view. If no user is authenticated, returns an empty list.
        """
        if not self.request.user.is_authenticated:
            return []
        app = self.kwargs.get('app')
        model_name = self.kwargs.get('model')
        return [f"{app}.{action}_{model_name}" for action in self.get_actions()]

    def handle_no_permission(self):
        """
        Override the default permission handling to provide a custom message
        and redirect to the referer or login page.
        """
        if self.get_permission_required():
            messages.warning(self.request, _("You don't have permission to perform this action."))
        # Redirect back to the previous page (or to 'login' as a fallback)
        return HttpResponseRedirect(self.request.META.get('HTTP_REFERER', reverse_lazy('login')))

    def get_content_type(self):
        """
        Return the ContentType for the model based on URL kwargs.
        """
        app = self.kwargs['app']
        model_name = self.kwargs['model']
        return ContentType.objects.get(app_label=app, model=model_name)

    def get_model(self):
        """
        Retrieve the model class based on the 'app' and 'model' values in the URL kwargs.
        """
        app = self.kwargs['app']
        model_name = self.kwargs['model']
        return apps.get_model(app, model_name=model_name)

    def keywords(self):
        """
        Generate a list of keyword dictionaries to be used (for example, in
        filtering or search functionality). Each keyword dictionary contains
        a 'name', 'meta', and 'value'. Additionally, custom models can be
        added by uncommenting the code below.
        """
        _keywords = [
            {'name': _('vrai'), 'meta': 'boolean', 'value': 'True'},
            {'name': _('faux'), 'meta': 'boolean', 'value': 'False'},
            {'name': _('null'), 'meta': 'null', 'value': 'None'},
            {'name': _('vide'), 'meta': 'empty', 'value': ''},
            {'name': _('aujourdhui'), 'meta': 'date', 'value': 'datetime.date.today()'},
            {'name': _('maintenant'), 'meta': 'datetime', 'value': 'datetime.datetime.now()'}
        ]
        # Example: Insert custom models as needed by uncommenting and adding to the list.
        custom_models = [
            # apps.get_model('employee.employee'),
            # apps.get_model('payroll.payroll'),
            # apps.get_model('payroll.payslip'),
        ]
        exclude_fields = ['created_by', 'updated_by', 'updated_at', 'created_at']
        for model_class in custom_models:
            # Loop through all fields in each custom model.
            for field in model_class._meta.fields:
                if field.name in exclude_fields:
                    continue
                if not field.is_relation:
                    _keywords.append({
                        'name': f'{model_class._meta.model_name}.{field.verbose_name.lower()}',
                        'value': f'{model_class._meta.model_name}.{field.name}',
                        'meta': model_class._meta.verbose_name.lower(),
                    })
                else:
                    # If the field is a relation and has a related model, iterate through its fields.
                    if not field.related_model:
                        continue
                    related_model = field.related_model
                    for related_field in related_model._meta.fields:
                        if related_field.name in exclude_fields:
                            continue
                        _keywords.append({
                            'name': related_field.verbose_name.lower(),
                            'meta': related_model._meta.verbose_name.lower(),
                            'value': f"{model_class._meta.model_name}.{field.name}.{related_field.name}"
                        })
        return _keywords

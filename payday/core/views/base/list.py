from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import redirect, render
from django.apps import apps
from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from core.filters import filter_set_factory
from core.forms.button import Button
from django.contrib import messages
from .base import BaseViewMixin
import logging

logger = logging.getLogger(__name__)

class List(BaseViewMixin):
    action = ["view"]
    template_name = "list.html"

    def dispatch(self, request, *args, **kwargs):
        """
        Middleware-style permission check before processing the request.
        If the user lacks view permission, they are redirected to the home page with a warning.
        """
        model_class = self.model_class
        view_perm = f"{model_class._meta.app_label}.view_{model_class._meta.model_name}"

        if not request.user.has_perm(view_perm):
            messages.warning(request, _("You do not have permission to view this page."))
            return redirect(reverse_lazy("core:home"))

        return super().dispatch(request, *args, **kwargs)

    def get_action_buttons(self, obj=None):
        """
        Build action buttons dynamically based on user permissions.
        """
        app_label, model_name = self.kwargs['app'], self.kwargs['model']

        action_buttons = [
            Button(
                tag='button',
                text=_('Supprimer'),
                permission=f"{app_label}.delete_{model_name}",
                classes='btn btn-light-danger btn-list-action',
                attrs={'data-action': reverse_lazy('core:delete', kwargs={'app': app_label, 'model': model_name})}
            ),
            Button(
                tag='button',
                text=_('Exporter'),
                permission=f"{app_label}.view_{model_name}",
                classes='btn btn-light-warning btn-list-action',
                attrs={'data-action': reverse_lazy('core:exporter', kwargs={'app': app_label, 'model': model_name})}
            ),
            Button(
                tag='a',
                text=_('Ajouter'),
                classes='btn btn-light-success',
                permission=f"{app_label}.add_{model_name}",
                url=reverse_lazy('core:create', kwargs={'app': app_label, 'model': model_name})
            ),
        ]

        return [button for button in action_buttons if self.request.user.has_perm(button.permission)]

    def get_list_filter(self):
        """Retrieve filtering fields from the model."""
        return getattr(self.model_class(), 'list_filter', [])

    def get_list_display(self):
        """Retrieve and order display fields defined in the model."""
        model_class = self.model_class()
        list_display = getattr(model_class, 'list_display', [])
        order_map = {name: i for i, name in enumerate(list_display)}

        return sorted(
            [field for field in model_class._meta.fields if field.name in list_display],
            key=lambda field: order_map.get(field.name, float('inf'))
        )

    def widgets(self):
        """Retrieve related widgets if the user has view permissions."""
        model_class = self.model_class()
        app_label, model_name = model_class._meta.app_label.lower(), model_class._meta.model_name.lower()
        required_permission = f"{app_label}.view_{model_name}"

        if not self.request.user.has_perm(required_permission):
            return []

        widget_model = apps.get_model('core.widget')
        return widget_model.objects.filter(content_type__app_label=app_label, content_type__model=model_name)

    def get(self, request, app, model):
        """
        Handles GET requests for the list view.
        Applies filters, paginates the queryset, and renders the template.
        """
        model_class = apps.get_model(app, model_name=model)

        # Redirect special cases
        if model_class._meta.model_name == 'notifications':
            return redirect(reverse_lazy('core:notifications'))

        if hasattr(model_class, 'list_url'):
            return redirect(getattr(model_class, 'list_url'))

        # Apply filtering
        qs = self.get_queryset()
        filter_set_class = filter_set_factory(model_class, fields=self.get_list_filter())
        filter_set = filter_set_class(request.GET, queryset=qs)
        qs = filter_set.hard_filter()

        # Apply ordering and pagination
        page_number = request.GET.get('page', 1)
        order_column = f'-{model_class._meta.pk.name}'
        paginator = Paginator(qs.order_by(order_column), 100)

        try:
            page_obj = paginator.page(page_number)
        except (EmptyPage, PageNotAnInteger):
            page_obj = paginator.page(1)

        action_buttons = self.get_action_buttons()
        return render(request, self.get_template_name(), locals())

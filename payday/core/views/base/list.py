from core.filters import filter_set_factory
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.apps import apps
from core.forms.button import Button
from .base import BaseView
from django.utils.translation import gettext as _
from django.urls import reverse_lazy


class List(BaseView):
    action = ["view"]
    template_name = "list.html"

    def get_action_buttons(self):
        """
        Build the action buttons for the list view.
        Each button includes inline JavaScript (for redirecting using getSelectedRows)
        and is only returned if the current user has permission.
        """
        kwargs = {
            'app': self.kwargs['app'],
            'model': self.kwargs['model']
        }
        
        delete_url = reverse_lazy('core:delete', kwargs=kwargs)
        export_url = reverse_lazy('core:exporter', kwargs=kwargs)
        create_url = reverse_lazy('core:create', kwargs=kwargs)

        action_buttons = [
            Button(**{
                'text': _('Supprimer'),
                'tag': 'button',
                'classes': 'btn btn-light-danger selected',
                'permission': f'{kwargs["app"]}.delete_{kwargs["model"]}',
                'attrs': {
                    # Inline JS to redirect including the selected rows as id__in query parameter.
                    'onclick': (
                        "window.location.href = '{}?pk__in=' + "
                        "getSelectedRows('table').join(',');"
                    ).format(delete_url)
                }
            }),
            Button(**{
                'text': _('Exporter'),
                'tag': 'button',
                'classes': 'btn btn-light-info',
                'permission': f'{kwargs["app"]}.view_{kwargs["model"]}',
                'attrs': {
                    'onclick': (
                        "window.location.href = '{}?pk__in=' + "
                        "getSelectedRows('table').join(',');"
                    ).format(export_url)
                }
            }),
            Button(**{
                'text': _('Ajouter'),
                'tag': 'a',
                'url': create_url,
                'classes': 'btn btn-light-success',
                'permission': f'{kwargs["app"]}.add_{kwargs["model"]}'
            }),
        ]

        # Filter buttons based on user permissions.
        return [button for button in action_buttons if self.request.user.has_perm(button.permission)]

    def get_list_filter(self):
        """
        Return the list_filter fields defined on the model.
        """
        model_class = self.get_model()
        return getattr(model_class, 'list_filter', [])

    def get_list_display(self):
        """
        Return the list_display fields in the order defined on the model.
        """
        model_class = self.get_model()
        # Get the list_display attribute from the model, or an empty list if not defined.
        list_display = getattr(model_class, 'list_display', [])
        # Create an order mapping based on the order in list_display.
        list_display_order = {name: i for i, name in enumerate(list_display)}
        # Filter the model fields that are in list_display.
        fields_to_display = [field for field in model_class._meta.fields if field.name in list_display]
        # Sort fields based on their defined order.
        return sorted(fields_to_display, key=lambda field: list_display_order[field.name])

    def widgets(self):
        """
        Returns related widget objects for the model if the user has required permissions.
        """
        model_class = self.get_model()
        app_label = model_class._meta.app_label.lower()
        model_name = model_class._meta.model_name.lower()
        required_permission = f"{app_label}.view_{model_name}"
        if not self.request.user.has_perm(required_permission):
            return []

        # Retrieve the widget model and filter by the relevant content type.
        widget_model = apps.get_model('core.widget')
        return widget_model.objects.filter(
            content_type__app_label=app_label,
            content_type__model=model_name
        )

    def get(self, request, app, model):
        """
        Handles the GET request for the list view.
        Retrieves the model, applies filters, paginates the queryset,
        and renders the template with the provided context.
        """
        # Retrieve the model class based on the app and model parameters.
        model_class = apps.get_model(app, model_name=model)

        # Special handling for notifications view.
        if model_class._meta.model_name == 'notifications':
            return redirect(reverse_lazy('core:notifications'))

        # If a custom list URL is defined on the model, redirect to it.
        if hasattr(model_class, 'list_url'):
            return redirect(getattr(model_class, 'list_url'))

        # Get the base queryset (likely defined in BaseView).
        qs = self.get_queryset().select_related().prefetch_related()

        # Apply soft filters based on the model's list_filter.
        filter_set_class = filter_set_factory(model_class, fields=self.get_list_filter())
        filter_set = filter_set_class(request.GET, queryset=qs)
        qs = filter_set.hard_filter()

        # Order queryset descending by primary key and set up pagination.
        order_column = f'-{model_class._meta.pk.name}'
        paginator = Paginator(qs.order_by(order_column), 100)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.page(int(page_number))

        return render(request, self.get_template_name(), locals())

from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import Http404
from django.contrib.admin.models import LogEntry, DELETION
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from django.db import transaction
from core.forms.button import Button
from .base import BaseView
import logging

logger = logging.getLogger(__name__)

class Delete(BaseView):
    """
    View for handling deletion of model objects based on GET query parameters.

    Requires query parameters to define which objects to delete. Validates permissions,
    constructs action buttons, and logs deletions. Supports redirecting to a 'next' URL
    or the list view after deletion.

    Attributes:
        template_name (str): Template for rendering the deletion confirmation page.
        action (list): Action type for this view (["delete"]).
        MAX_DELETE_LIMIT (int): Maximum number of objects that can be deleted in one request.
    """
    template_name = "delete.html"
    action = ["delete"]
    MAX_DELETE_LIMIT = 100  # Prevent accidental mass deletions

    def dispatch(self, request, *args, **kwargs):
        """
        Validates user permissions before processing the request.

        Args:
            request (HttpRequest): The incoming request.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: Redirects to home if permission is lacking, else proceeds.
        """
        model_class = self.get_model()
        delete_perm = f"{model_class._meta.app_label}.delete_{model_class._meta.model_name}"

        if not request.user.has_perm(delete_perm):
            messages.warning(request, _("Vous n'avez pas la permission de supprimer cet objet."))
            return redirect(reverse_lazy("core:home"))

        self.next = request.GET.get('next')
        return super().dispatch(request, *args, **kwargs)

    def get_action_buttons(self, obj=None):
        """
        Constructs action buttons (Cancel and Delete) for the deletion confirmation view.

        Includes model-specific buttons if defined, filtered by user permissions.

        Args:
            obj: Optional model instance for context-specific buttons (unused here).

        Returns:
            list: A list of Button objects filtered by user permissions.
        """
        app = self.kwargs['app']
        model_str = self.kwargs['model']
        model_permission_prefix = f"{app}.{model_str}"

        buttons = [
            Button(
                text=_('Cancel'),
                tag='a',
                url=reverse_lazy('core:list', kwargs={'app': app, 'model': model_str}),
                classes='btn btn-light-success',
                permission=f"{model_permission_prefix}.view"
            ),
            Button(
                text=_('Supprimer'),
                tag='button',
                classes='btn btn-danger',
                permission=f"{model_permission_prefix}.delete",
                attrs={'type': 'submit', 'form': f"form-{model_str}"}
            )
        ]

        # Handle model-specific extra buttons
        model = self.get_model()
        get_action_buttons = getattr(model, 'get_action_buttons', [])
        extra_buttons = [Button(**button) for button in get_action_buttons]

        return [btn for btn in buttons + extra_buttons]

    def _build_query_params(self, request):
        """
        Builds a dictionary of query parameters from GET parameters.

        Splits values for keys containing '__in' into lists. Validates parameters against
        model fields to prevent invalid lookups.

        Args:
            request (HttpRequest): The incoming request.

        Returns:
            dict: Query parameters with processed values.

        Raises:
            ValueError: If query parameters contain invalid field names.
        """
        query_params = {}
        model_fields = ['pk']
        model_fields += list({field.name for field in self.get_model()._meta.fields})

        for key, value in request.GET.dict().items():
            # Extract field name from lookup (e.g., 'id__in' -> 'id')
            field_name = key.split('__')[0]
            if field_name not in model_fields:
                logger.warning(f"Invalid field in query parameter: {field_name}")
                raise ValueError(_(f"Invalid field in query: {field_name}"))
            query_params[key] = value.split(',') if '__in' in key else value

        return query_params

    def get(self, request, app, model):
        """
        Handles GET requests by validating query parameters, building the queryset,
        and rendering the deletion confirmation template.

        Args:
            request (HttpRequest): The incoming GET request.
            app (str): The app label.
            model (str): The model name.

        Returns:
            HttpResponse: Rendered confirmation template.

        Raises:
            Http404: If no query parameters are provided.
        """
        try:
            model_class = self.get_model()
            query_params = self._build_query_params(request)

            if not query_params:
                logger.error(f"No query parameters provided for delete action on {model_class._meta.model_name}")
                raise Http404(_("Query is required for delete action"))

            # Extract and remove 'next' URL parameter
            next_url = query_params.pop('next', self.next or reverse_lazy(
                'core:list', kwargs={'app': app, 'model': model_class._meta.model_name}
            ))

            # Build queryset with optimization
            qs = self.get_queryset().filter(**query_params).select_related()
            if qs.count() > self.MAX_DELETE_LIMIT:
                messages.error(request, _(f"Cannot delete more than {self.MAX_DELETE_LIMIT} objects at once."))
                return redirect(next_url)

            action_buttons = self.get_action_buttons()
            return render(request, self.template_name, locals())

        except ValueError as e:
            logger.error(f"Invalid query parameters for delete action: {str(e)}")
            messages.error(request, str(e))
            return redirect(self.next or reverse_lazy('core:home'))
        except Exception as e:
            logger.error(f"Error processing GET request for delete action: {str(e)}")
            messages.error(request, _("Une erreur est survenue lors du chargement de la page de suppression."))
            return redirect(self.next or reverse_lazy('core:home'))

    @transaction.atomic
    def post(self, request, app, model):
        """
        Handles POST requests by validating query parameters, performing deletion,
        logging the action, and redirecting.

        Args:
            request (HttpRequest): The incoming POST request.
            app (str): The app label.
            model (str): The model name.

        Returns:
            HttpResponse: Redirect to the next URL or list view.

        Raises:
            Http404: If no query parameters are provided.
        """
        model_class = self.get_model()
        query_params = self._build_query_params(request)

        if not query_params:
            logger.error(f"No query parameters provided for delete action on {model_class._meta.model_name}")
            raise Http404(_("Query is required for delete action"))

        # Extract 'next' parameter
        next_url = query_params.pop('next', self.next or reverse_lazy(
            'core:list', kwargs={'app': app, 'model': model_class._meta.model_name}
        ))

        # Build and validate queryset
        qs = self.get_queryset().filter(**query_params).select_related()
        if qs.count() > self.MAX_DELETE_LIMIT:
            logger.warning(f"Attempted to delete more than {self.MAX_DELETE_LIMIT} objects")
            messages.error(request, _(f"Cannot delete more than {self.MAX_DELETE_LIMIT} objects at once."))
            return redirect(next_url)

        # Log deletion
        pk_field = model_class._meta.pk.name
        object_ids = list(qs.values_list(pk_field, flat=True))
        if object_ids:
            id_str = ", ".join(str(obj_id) for obj_id in object_ids)
            LogEntry.objects.log_action(
                user_id=request.user.id,
                content_type_id=ContentType.objects.get_for_model(model_class).id,
                object_id=None,
                object_repr=f"Object(s) deletion: {id_str}",
                action_flag=DELETION,
            )

        # Perform deletion
        messages.success(request, _(f"{len(object_ids)} object(s) deleted successfully"))
        return redirect(next_url)
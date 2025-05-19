from django.utils.translation import gettext as _
from django.shortcuts import render, redirect
from django.http import Http404
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import transaction
from django.contrib.admin.models import CHANGE
from core.forms import modelform_factory, InlineFormSetHelper
from core.forms.button import Button
from core.models import Preference
from .base import BaseView
import logging

logger = logging.getLogger(__name__)

from django.shortcuts import redirect
from django.urls import reverse_lazy

class Change(BaseView):
    """
    View for changing/updating a model instance with permission validation middleware.
    """

    next = None
    action = ["change"]
    template_name = "change.html"
    inline_formset_helper = InlineFormSetHelper()

    def dispatch(self, request, *args, **kwargs):
        """
        Middleware-like permission check before processing the request.

        If the user lacks change permission, redirect them to the Read view.
        """
        model_class = self.get_model()
        change_perm = f"{model_class._meta.app_label}.change_{model_class._meta.model_name}"

        if not request.user.has_perm(change_perm):
            return redirect(reverse_lazy('core:read', kwargs=kwargs))

        return super().dispatch(request, *args, **kwargs)

    def _get_object(self):
        """
        Efficiently retrieve the model instance using `select_related()` when applicable.

        Raises:
            Http404: If no primary key is provided or no matching instance is found.

        Returns:
            instance: The model instance, or None if not found.
        """
        model_class = self.get_model()
        pk = self.kwargs.get('pk', None)
        if not pk:
            raise Http404(_('Aucun identifiant n\'a été fourni'))

        obj = self.get_queryset().select_related().filter(**{model_class._meta.pk.name: pk}).first()
        if not obj:
            logger.warning(f"{model_class._meta.model_name} ID {pk} not found.")
            raise Http404(_('Le {model} #{pk} n\'existe pas').format(model=model_class._meta.model_name, pk=pk))

        return obj

    def get_action_buttons(self, obj=None):
        """
        Constructs action buttons (e.g., Delete, Save) for the change view.
        Buttons are displayed only if the user has the required permissions.

        Args:
            obj (ModelInstance, optional): The instance for which action buttons are generated.

        Returns:
            list: A list of permitted Button objects.
        """
        obj = obj or self._get_object()
        kwargs = {'app': self.kwargs['app'], 'model': self.kwargs['model']}
        model_permission_prefix = f"{kwargs['app']}.{kwargs['model']}"

        # Retrieve additional buttons safely with a default empty list
        extra_buttons = (Button(**button) for button in getattr(obj, 'get_action_buttons', []))

        # Define standard action buttons efficiently
        buttons = (
            Button(
                tag='a',
                text=_('Supprimer'),
                classes='btn btn-light-danger',
                permission=f"{model_permission_prefix}.delete",
                url=f"{reverse_lazy('core:delete', kwargs=kwargs)}?pk__in={obj.pk}"
            ),
            Button(
                tag='button',
                text=_('Sauvegarder'),
                classes='btn btn-light-success',
                permission=f"{model_permission_prefix}.change",
                attrs={'type': 'submit', 'form': f"form-{kwargs['model']}"}
            )
        )

        # Return only buttons for which the user has the required permissions
        return [button for button in (*extra_buttons, *buttons) if self.request.user.has_perm(button.permission)]


    def get_formsets(self, obj):
        """
        Lazily generate formsets for better memory efficiency.
        """
        return (fs(instance=obj) for fs in self.formsets())

    def get(self, request, app, model, pk):
        """
        Handle GET requests efficiently by preloading related data.

        Returns:
            HttpResponse: The rendered response.
        """
        model_class = self.get_model()
        obj = self._get_object()

        if model_class._meta.model_name == 'notification':
            obj.mark_as_read()
            return redirect(obj.target.get_absolute_url() if obj.target else reverse_lazy('core:notifications'))

        FormClass = modelform_factory(model_class, fields=self.get_form_fields())
        form = self.filter_form(FormClass(instance=obj))
        formsets = list(self.formsets())
        
        action_buttons = self.get_action_buttons(obj=obj)
        return render(request, self.get_template_name(), locals())

    @transaction.atomic
    def post(self, request, app, model, pk):
        """
        Handle POST requests efficiently while improving error handling and validation.

        Returns:
            HttpResponse or HttpResponseRedirect.
        """
        model_class = self.get_model()
        obj = self._get_object()

        FormClass = modelform_factory(model_class, fields=self.get_form_fields())
        form = self.filter_form(FormClass(request.POST, request.FILES, instance=obj))
        formsets = self.formsets()

        for fs in formsets:
            print(f"IS VALID : {fs.is_valid()}")

        is_valid_formset = bool(formsets) and any(not fs.is_valid() for fs in formsets)
        if not form.is_valid() or is_valid_formset:
            for error in form.errors.values():
                messages.warning(request, error)

            for fs in formsets:
                for formset_error in fs.errors:
                    messages.warning(request, formset_error)

            action_buttons = self.get_action_buttons(obj=obj)
            return render(request, self.get_template_name(), locals())

        # Save changes
        form.save()
        formsets = [fs.save() for fs in formsets]

        # Log change
        change_message = self.generate_change_message(obj, form.instance)
        self.log(model_class, form, action=CHANGE, change_message=change_message)

        messages.success(request, _('Le {model} #{pk} a été mis à jour avec succès').format(model=model_class._meta.model_name, pk=pk))
        return redirect(request.GET.get('next', reverse_lazy('core:list', kwargs={'app': app, 'model': model_class._meta.model_name})))

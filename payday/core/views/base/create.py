from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from django.contrib import messages

from django.contrib.admin.models import ADDITION
from django.shortcuts import render, redirect
from django.db import transaction

from core.forms import modelform_factory, InlineFormSetHelper
from core.forms.button import Button
from .base import BaseView


class Create(BaseView):
    """
    View for creating a new instance of a model, with support for inline formsets.
    """

    next = None
    action = ["add"]
    template_name = "create.html"
    inline_formset_helper = InlineFormSetHelper()

    def dispatch(self, request, *args, **kwargs):
        """Permission check before processing the request."""
        model_class = self.get_model()
        add_perm = f"{model_class._meta.app_label}.add_{model_class._meta.model_name}"

        if not request.user.has_perm(add_perm):
            return redirect(reverse_lazy("core:home"))

        return super().dispatch(request, *args, **kwargs)

    def get_action_buttons(self):
        """Generates action buttons dynamically based on user permissions."""
        kwargs = {'app': self.kwargs['app'], 'model': self.kwargs['model']}
        user = self.request.user

        buttons = [
            Button(
                text=_('Annuler'),
                tag='a',
                url=reverse_lazy('core:list', kwargs=kwargs),
                classes='btn btn-light-danger',
                permission=f"{kwargs['app']}.delete_{kwargs['model']}"
            ),
            Button(
                text=_('Sauvegarder'),
                tag='button',
                classes='btn btn-success',
                permission=f"{kwargs['app']}.add_{kwargs['model']}",
                attrs={'type': 'submit', 'form': f"form-{kwargs['model']}"}
            ),
        ]

        extra_buttons = [
            Button(**button) for button in getattr(self.get_model(), 'get_action_buttons', lambda: [])()
        ]

        return [btn for btn in (*extra_buttons, *buttons) if user.has_perm(btn.permission)]

    def get(self, request, app, model):
        """Handles GET requests by initializing the form and inline formsets."""
        model_class = self.get_model()

        initial = {
            'employee': getattr(request.user, 'employee', None),
            **request.GET.dict()
        }

        form = modelform_factory(model_class, fields=self.get_form_fields())
        form = form(initial=initial)
        form = self.filter_form(form)
        formsets = [formset() for formset in self.formsets()]
        return render(request, self.get_template_name(), locals())

    @transaction.atomic
    def post(self, request, app, model):
        """Processes form submissions and ensures atomic transactions."""
        model_class = self.get_model()

        initial = {
            'employee': getattr(request.user, 'employee', None),
            **request.GET.dict()
        }

        form = modelform_factory(model_class, fields=self.get_form_fields())
        form = form(request.POST, request.FILES, initial=initial)
        form = self.filter_form(form)
        formsets = [formset(request.POST, request.FILES) for formset in self.formsets()]

        if not form.is_valid() or any(not fs.is_valid() for fs in formsets):
            messages.warning(request, _("Veuillez corriger les erreurs avant de soumettre."))
            return render(request, self.get_template_name(), locals())

        # Save main instance
        instance = form.save()

        # Save inline instances and link them to main instance
        for formset in formsets:
            for obj in formset.save(commit=False):
                setattr(obj, formset.fk.name, instance)
                obj.save()

        # Log addition
        message = _('Ajout du/de {model} #{pk}').format(model=model_class._meta.model_name, pk=instance.pk)
        self.log(model_class, form, action=ADDITION, change_message=self.generate_change_message(instance, form.instance))
        messages.success(request, message)

        return redirect(request.GET.get('next', reverse_lazy('core:list', kwargs={'app': app, 'model': model_class._meta.model_name})))

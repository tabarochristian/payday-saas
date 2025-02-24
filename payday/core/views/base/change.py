from django.utils.translation import gettext as _
from django.shortcuts import render, redirect
from django.http import Http404

from core.forms.button import Button
from django.contrib import messages

from core.forms import modelform_factory, InlineFormSetHelper
from django.urls import reverse_lazy
from django.db import transaction

from django.contrib.admin.models import CHANGE
from core.models import Preference
from .base import BaseView
import copy


class Change(BaseView):
    next = None
    action = ["change"]
    template_name = "change.html"
    inline_formset_helper = InlineFormSetHelper()

    def safe_eval(self, key, value):
        allowed_names = {'int': int, 'float': float, 'str': str, 'bool': bool, 'list': list}
        try:
            return eval(f'{key}("{value}")', {"__builtins__": allowed_names}, {})
        except:
            return value

    def preferences(self):
        prefs = Preference.objects.all().values('key', 'value')
        return {
            pref.get('key').split(':')[0].lower(): self.safe_eval(pref.get('key').split(':')[-1].lower(), pref.get('value'))
            for pref in prefs
        }


    def _get_object(self):
        model = self.get_model()
        pk = self.kwargs.get('pk', None)
        if not pk:
            raise Http404(_('Aucun identifiant n\'a été fourni'))
        return self.get_queryset().filter(**{model._meta.pk.name: pk}).first()

    def get_action_buttons(self):
        obj = self._get_object()
        kwargs = {'app': self.kwargs['app'], 'model': self.kwargs['model']}

        action_buttons = getattr(obj, 'get_action_buttons', [])
        action_buttons = [Button(**button) for button in action_buttons]

        action_buttons = action_buttons + [
            Button(**{
                'text': _('Annuler'),
                'tag': 'a',
                'url': reverse_lazy('core:list', kwargs=kwargs),
                'classes': 'btn btn-light-success',
                'permission': f'{kwargs['app']}.view_{kwargs['model']}'
            }), 
            Button(**{
                'text': _('Supprimer'),
                'tag': 'a',
                'url': reverse_lazy('core:delete', kwargs=kwargs)+f'?pk__in={obj.pk}',
                'classes': 'btn btn-light-danger',
                'permission': f'{kwargs['app']}.delete_{kwargs['model']}'
            }),
            Button(**{
                'text': _('Sauvegarder'),
                'tag': 'button',
                'classes': 'btn btn-light-success',
                'permission': f'{kwargs['app']}.change_{kwargs['model']}',
                'attrs': {
                    'type': 'submit',
                    # 'name': '_save',
                    'form': f'form-{kwargs["model"]}'
                }
            }),
            #Button(**{
            #    'text': _('Sauvegarder et continuer les modifications'),
            #    'tag': 'button',
            #    'classes': 'btn btn-light-success',
            #    'permission': f'{kwargs['app']}.change_{kwargs['model']}',
            #    'attrs': {
            #        'type': 'submit',
            #        'name': '_continue',
            #        'form': f'form-{kwargs["model"]}'
            #    }
            #   })
        ]

        # make sure the user has the permission to see the button
        return [button for button in action_buttons if self.request.user.has_perm(button.permission)]

    def get(self, request, app, model, pk):
        model = self.get_model()
        obj = self._get_object()
        
        if not obj:
            message = _('Le {model} #{pk} n\'existe pas')
            messages.warning(request, message.format(**{'model': model._meta.model_name, 'pk': pk}))
            return redirect(reverse_lazy('core:list', kwargs={'app': app, 'model': model._meta.model_name}))
        
        form = modelform_factory(model, fields=self.get_form_fields())
        form = form(instance=obj)
        form = self.filter_form(form)

        formsets = [formset(instance=obj) for formset in self.formsets()]
        return render(request, self.get_template_name(), locals())

    @transaction.atomic
    def post(self, request, app, model, pk):
        model = self.get_model()
        obj = self._get_object()

        instance = copy.copy(obj)
        
        form = modelform_factory(model, fields=self.get_form_fields())
        form = form(request.POST or None, request.FILES or None, instance=obj)
        form = self.filter_form(form)

        formsets = [formset(request.POST or None, request.FILES or None, instance=obj) for formset in self.formsets()]

        if not all(formset.is_valid() for formset in [form] + formsets):
            for error in form.errors: messages.warning(request, str(error))
            return render(request, self.get_template_name(), locals())

        form.save()
        [formset.save() for formset in formsets]

        message = _('Le {model} #{pk} a été mis à jour avec succès')
        self.log(model, form, action=CHANGE, change_message=self.generate_change_message(instance, form.instance))
        messages.add_message(request, messages.SUCCESS,  message=message.format(**{'model': model._meta.model_name, 'pk': pk}))

        redirect_to = reverse_lazy('core:list', kwargs={'app': app, 'model': model._meta.model_name})
        return redirect(request.GET.dict().get('next', redirect_to))
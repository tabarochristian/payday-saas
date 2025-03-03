from django.shortcuts import render, redirect
from django.http import Http404

from django.contrib.admin.models import LogEntry, DELETION
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from core.forms.button import Button
from .base import BaseView


class Delete(BaseView):
    next = None
    action = ["delete"]
    template_name = "delete.html"

    def get_action_buttons(self):
        app, model = self.kwargs['app'], self.kwargs['model']
        action_buttons = getattr(self.get_model(), 'get_action_buttons()', [])
        action_buttons = [Button(**button) for button in action_buttons]

        return [
            Button(**{
                'text': _('Cancel'),
                'tag': 'a',
                'url': reverse_lazy('core:list', kwargs={
                    'app': app, 
                    'model': model
                }),
                'classes': 'btn btn-light-success'
            }),
            Button(**{
                'text': _('Supprimer'),
                'tag': 'button',
                'classes': 'btn btn-danger',
                'permission': f'{app}.delete_{model}',
                'attrs': {
                    'type': 'submit',
                    'form': f'form-{model}'
                }
            }),
        ] + action_buttons
    
    def get(self, request, app, model):
        model = self.get_model()
        query = {k:v.split(',') if '__in' in k else v for k, v in request.GET.dict().items()}

        if not query:
            raise Http404(_("Query is required for delete action"))
        
        next = query.pop('next', None)
        qs = self.get_queryset().filter(**query)
        return render(request, self.template_name, locals())

    def post(self, request, app, model):
        model = self.get_model()
        query = {k:v.split(',') if '__in' in k else v for k, v in request.GET.dict().items()}

        if not query:
            raise Http404(_("Query is required for delete action"))
        
        next = query.pop('next', reverse_lazy('core:list', kwargs={'app': app, 'model': model._meta.model_name}))
        qs = self.get_queryset().filter(**query)
        

        # To-Do: To prevent delete of approved object by creator
        LogEntry.objects.log_action(**{
            'user_id': request.user.id,
            'content_type_id': ContentType.objects.get_for_model(model).id,
            'object_id': obj.pk,
            'object_repr': force_str(obj),
            'action_flag': DELETION
        })
        qs.delete()
        return redirect(next) if next else render(request, self.template_name, locals())
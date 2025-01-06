from core.filters import filter_set_factory
from django.core.paginator import Paginator
from django.shortcuts import redirect
from core.forms.button import Button
from django.shortcuts import render
from django.apps import apps
from .base import BaseView

from django.utils.translation import gettext as _
from django.urls import reverse_lazy


class List(BaseView):
    action = ["view"]
    template_name = "list.html"

    def get_action_buttons(self):
        kwargs = {'app': self.kwargs['app'], 'model': self.kwargs['model']}

        action_buttons = getattr(self.get_model(), 'get_action_buttons()', [])
        action_buttons = [Button(**button) for button in action_buttons]

        action_buttons = [
            Button(**{
                'text': _('Supprimer'),
                'tag': 'a',
                'url': reverse_lazy('core:delete', kwargs=kwargs),
                'classes': 'btn btn-light-danger selected',
                'permission': f'{kwargs['app']}.delete_{kwargs['model']}'
            }),
            Button(**{
                'text': _('Exportateur'),
                'tag': 'a',
                'url': reverse_lazy('core:exporter', kwargs=kwargs),
                'classes': 'btn btn-light-info',
                'permission': f'{kwargs['app']}.view_{kwargs['model']}'
            }),
            Button(**{
                'text': _('Ajouter'),
                'tag': 'a',
                'url': reverse_lazy('core:create', kwargs=kwargs),
                'classes': 'btn btn-light-success',
                'permission': f'{kwargs['app']}.add_{kwargs['model']}'
            }),
        ] + action_buttons

        return [button for button in action_buttons if self.request.user.has_perm(button.permission)]
    

    def get_list_filter(self):
        model = self.get_model()
        return getattr(model, 'list_filter', [])

    def get_list_display(self):
        model = self.get_model()
        list_display = getattr(model, 'list_display', [])
        list_display_order = {field: i for i, field in enumerate(list_display)}
        return sorted([field for field in model._meta.fields 
                       if field.name in list_display], key=lambda field: list_display_order[field.name])

    def widgets(self):
        model = self.get_model()
        app_label, model_name = model._meta.app_label, model._meta.model_name
        perm = f"{app_label}.view_{model_name}"
        if not self.request.user.has_perm(perm):
            return []
        
        return apps.get_model('core.widget').objects.filter(**{
            'content_type__app_label': model._meta.app_label.lower(),
            'content_type__model': model._meta.model_name.lower()
        })

    def get(self, request, app, model):
        model = apps.get_model(app, model_name=model)

        if hasattr(model, 'list_url'):
            return redirect(getattr(model, 'list_url'))

        # get queryset based on user 
        qs = self.get_queryset().select_related().prefetch_related()

        # apply soft filter based on list_filter
        filter = filter_set_factory(model, fields=self.get_list_filter())
        filter = filter(request.GET, queryset=qs)
        qs = filter.hard_filter()

        paginator = Paginator(qs.order_by('-id'), 100)
        qs = paginator.page(int(request.GET.dict().get('page', 1)))

        template = self.get_template_name()
        return render(request, template, locals())
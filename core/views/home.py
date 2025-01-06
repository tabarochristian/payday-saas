from django.utils.translation import gettext as _
from django.shortcuts import render
from core.models import Widget
from .base import BaseView



#@method_decorator(cache_page(60 * 15), name='dispatch')
class Home(BaseView):   
    template_name = "home.html"

    def get(self, request):
        widgets = [{
            'title': widget.name,
            'content': widget.render(request),
            'column': widget.column,
        } for widget in Widget.objects.all()]
        return render(request, self.template_name, locals())
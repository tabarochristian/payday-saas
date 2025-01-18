from django.shortcuts import render, get_object_or_404
from tenant.forms import crispy_modelform_factory
from django.http import JsonResponse

from tenant.models import Tenant
from django.views import View

class CreateTenantView(View):
    def get(self, request):
        form = crispy_modelform_factory(Tenant, exclude=["is_active"])
        form = form()
        return render(request, "index.html", locals())
    
    def post(self, request):
        form = crispy_modelform_factory(Tenant)
        form = form(request.POST)
        if not form.is_valid():
            return render(request, "index.html", locals())
        form.save()
        return render(request, "index.html", locals())
    
class TenantView(View):
    def get(self, request, pk):
        obj = get_object_or_404(Tenant, id=pk)
        return JsonResponse(obj.serialized)
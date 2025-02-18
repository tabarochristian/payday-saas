from django.shortcuts import render, get_object_or_404
from tenant.forms import crispy_modelform_factory
from django.utils.translation import gettext as _
from django.http import JsonResponse
from django.utils import translation

from django.forms import modelform_factory
from tenant.models import Tenant
from django.views import View

class CreateTenantView(View):

    meta_keywords = _(",".join([
        "Logiciel de paie en ligne",
        "Solution de gestion de la paie",
        "Paie automatisée pour entreprises",
        "Système de gestion des présences",
        "Paie et ressources humaines (RH)",
        "Logiciel SaaS de paie",
        "Gestion des salaires en RDC",
        "Pointage 4G pour entreprises",
        "Solution de paie flexible",
        "Gestion des congés et absences"
    ]))

    meta_description = _("Découvrez PayDay, la solution SaaS complète pour automatiser la paie, \
        gérer les présences avec un dispositif 4G et simplifier vos processus RH.")

    def get(self, request):
        form = crispy_modelform_factory(Tenant, exclude=["is_active"])
        return render(request, "index.html", locals())
    
    def post(self, request):
        form = crispy_modelform_factory(Tenant, exclude=["is_active"])
        form = form(request.POST)
        if not form.is_valid():
            return render(request, "index.html", locals())
        form.save()
        return render(request, "index.html", locals())
    
class TenantView(View):
    def get(self, request, pk):
        obj = get_object_or_404(Tenant, id=pk)
        return JsonResponse(obj.serialized)
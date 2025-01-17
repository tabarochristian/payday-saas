from django.http import HttpResponseRedirect
from core.utils import set_schema

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]
        try:
            schema_name = host.split('.')[0]
            set_schema(schema_name)
        except Exception as e:
            redirect_to = "https://payday.cd?message=not-found"
            return HttpResponseRedirect(redirect_to)

        response = self.get_response(request)
        return response
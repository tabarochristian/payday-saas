from django.http import HttpResponse
from django.views import View

class RobotsView(View):
    def get(self, request):
        return HttpResponse("\n".join([
            "User-Agent: *",
            "Disallow: /admin/",
            "Disallow: /private/",
            "Allow: /",
        ]), content_type="text/plain")

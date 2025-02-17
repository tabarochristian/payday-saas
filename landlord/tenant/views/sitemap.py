from django.template.loader import render_to_string
from django.http import HttpResponse
from django.views import View

class Sitemap(View):
    def get(self, request):
        sitemap_content = render_to_string('sitemap.xml', {})
        return HttpResponse(sitemap_content, content_type='application/xml')
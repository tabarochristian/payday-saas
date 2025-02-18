from django.contrib.sitemaps import Sitemap
from django.urls import reverse_lazy

class StaticViewSitemap(Sitemap):
    priority = 1.0
    protocol = 'https'
    changefreq = 'daily'

    def items(self):
        return ["tenant:create"] 

    def location(self, item):
        return reverse_lazy(item)

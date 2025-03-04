from django.http import HttpResponse
from core.views import BaseView

from employee.models import Employee
import pandas as pd

from django.utils.text import slugify
import json

class Canvas(BaseView):

    headers = [{
        'matricule': None,
        
        'type d\'element': 1,
        'code': None,
        'nom': None,

        #'temps': 0,
        #'taux': 0,
        
        'montant quote part employee': 0,
        'montant quote part employeur': 0,

        'plafond de la sécurité sociale': 0,
        'montant imposable': 0,

        'est une prime': 0,
        #'est payable': 1,
    }]

    def tracker(self):
        query = {k:v.split(',') if '__in' in k else v  for k,v in self.request.GET.dict().items() if v}
        qs = Employee.objects.filter(**query) \
            .values('registration_number', 'last_name', 'middle_name', 'branch__name', 'grade__name')
        
        columns = ['absence', 'absence.justifiee']
        field_no_numbers = []

        data = [{
            'registration_number': obj['registration_number'],
            'last_name': obj['last_name'],
            'middle_name': obj['middle_name'],
            'grade': obj['grade__name'],
            'branch': obj['branch__name'],
            **{k: None if k in field_no_numbers else 0 for k in columns}
        } for obj in qs]

        group_by = 'branch'
        df = pd.read_json(json.dumps(data), dtype={'registration_number': str})

        if not df.empty:
            df = df.sort_values(by=['grade', 'registration_number', 'last_name', 'middle_name'], 
                                ascending=[True, True, True, True])
            df = df.groupby(group_by)
        
        response = HttpResponse(content_type='application/xlsx')
        response['Content-Disposition'] = f'attachment; filename="canvas.xlsx"'.lower()

        with pd.ExcelWriter(response) as writer:
            [group.to_excel(writer, sheet_name=slugify(str(row)), index=False) 
                for row, group in df] if group_by else df.to_excel(writer, sheet_name='global', index=False)
        return response

    def benefits(self):
        df = pd.read_json(json.dumps(self.headers))
        response = HttpResponse(content_type='application/xlsx')
        response['Content-Disposition'] = f'attachment; filename="canvas-items-to-pay.xlsx"'.lower()

        with pd.ExcelWriter(response) as writer:
            df.to_excel(writer, sheet_name='global', index=False)
        return response

    def get(self, request, actor):
        actor = getattr(self, actor)
        if not actor or not callable(actor):
            raise Http404("Page not found")
        return actor()


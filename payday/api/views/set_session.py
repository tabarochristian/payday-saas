from rest_framework.response import Response
from rest_framework.views import APIView

class SetSessionView(APIView):
    def post(self, request):
        for k, v in request.data.items():
            request.session[k] = eval(v)
        return Response(request.data)
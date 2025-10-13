from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

class SetSessionView(APIView):
    def post(self, request):
        for key, value in request.data.items():
            # Attempt to interpret basic types safely
            if value in ["null", "None"]:
                request.session.pop(key, None)
            else:
                request.session[key] = value
        return Response({"session": dict(request.session)}, status=status.HTTP_200_OK)

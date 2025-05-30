from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.utils.timezone import now
from api.serializer import EmployeeSerializer


class EmployeeSyncWithRollApp(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        data = request.data

        required_fields = [
            "idBiometrique", "NumDocument", "DatNais", "Sexe", "Etat_civil",
            "contact_number", "Adresse", "contact_email", "Pren", "postnom", "Noms", "photo",
            "fingerprint_left_thumb", "fingerprint_right_thumb",
        ]

        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return Response({"error": f"Champs requis manquants: {', '.join(missing)}"}, status=status.HTTP_400_BAD_REQUEST)

        employee_data = {
            "created_at": now(),
            "updated_at": now(),
            "registration_number": data.get("idBiometrique"),
            "social_security_number": data.get("NumDocument"),
            "date_of_birth": data.get("DatNais"),
            "gender": "MALE" if data.get("Sexe") == "M" else "FEMALE",
            "marital_status": data.get("Etat_civil"),
            "mobile_number": data.get("contact_number"),
            "physical_address": data.get("Adresse"),
            "email": data.get("contact_email"),
            "first_name": data.get("Pren"),
            "middle_name": data.get("postnom"),
            "last_name": data.get("Noms"),
            "create_user_on_save": False,
            "photo": request.FILES.get("photo", None),
            "payment_method": "MOBILE MONEY"
        }

        employee_data["_metadata"] = {
            key: value for key, value in data.items() if key not in required_fields
        }

        employee_data["_metadata"] = {
            **employee_data["_metadata"],
            "fingerprint_left_thumb": data.get("fingerprint_left_thumb"),
            "fingerprint_right_thumb": data.get("fingerprint_right_thumb"),
            "source": "rollapp",
            "source_id": data.get("idBiometrique"),
            "source_created_at": data.get("created_at", now().isoformat()),
            "source_updated_at": data.get("updated_at", now().isoformat())
        }

        try:
            serializer = EmployeeSerializer(data=employee_data)
            if serializer.is_valid():
                serializer.save()
                return Response({"data": serializer.data}, status=status.HTTP_201_CREATED)
            else:
                return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

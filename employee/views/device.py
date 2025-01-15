from employee.models import Device, Attendance
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework import status

from collections import defaultdict
from django.utils import timezone
from dateutil import parser

class DeviceView(APIView):

    def reg(self, data):
        sn = data.get("sn")
        obj, created = Device.objects.get_or_create(sn=sn)
        if created: print("Device created")
        obj.status = "connected"
        obj._metadata = data
        obj.save()
        return obj.serialized
    
    def disconnected(self, data):
        sn = data.get("sn")
        Device.objects.filter(sn=sn).update(status="disconnected")
        return {"status": "success"}
    
    def senduser(self, data):
        return {}
    
    def sendlog(self, data):
        today = timezone.now().date()
        sn = data.get("sn")

        # Fetch the device in a single query
        try:
            device = Device.objects.get(sn=sn)
        except Device.DoesNotExist:
            return {"error": "Device not found", "total": 0}

        # Filter records for today
        records = data.get("record", [])

        today_records = [
            item for item in records
            # if parser.parse(item.get('time', '2000-01-01')).date() == today
        ]

        # Group records by enrollid
        grouped_data = defaultdict(list)
        for item in today_records:
            enrollid = item['enrollid']
            time = item['time']
            grouped_data[enrollid].append(time)

        # Prepare final data with min and max times
        final_data = {
            enrollid: {
                "min_time": min(times),
                "max_time": max(times)
            }
            for enrollid, times in grouped_data.items()
        }

        # Prepare Attendance objects for bulk creation
        attendance_records = [
            Attendance(
                device=device, 
                employee_id=enrollid, 
                checked_at=time
            )
            for enrollid, times in final_data.items()
            for time in [times["min_time"], times["max_time"]]
        ]

        # Bulk create attendance records
        Attendance.objects.bulk_create(attendance_records, ignore_conflicts=True)
        return {"total": len(attendance_records)}


    def post(self, request):
        data = request.data
        cmd = data.get("cmd")
        sn = data.get("sn")

        if not cmd or not sn:
            return Response({"status": "error", "message": "Invalid data"}, status=status.HTTP_400_BAD_REQUEST)
        
        method = getattr(self, cmd, None)
        if method is None or not callable(method):
            return Response({"status": "error", "message": "Invalid command"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "success", "data": method(data)}, status=status.HTTP_200_OK)

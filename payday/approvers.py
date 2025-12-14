from core.utils import set_schema

set_schema("kazi")

data = {
    "00026276": [
        "00026387",
        "00026389",
        "00026455"
    ],
    "00026295": [
        "00026365",
        "00026456",
        "00026368",
        "00026363",
        "00026339",
        "00026367",
        "00026340",
        "00026454",
        "00026366",
        "00026359",
        "00026361",
        "00026470",
        "00026475",
        "00026477",
        "00026468",
        "00026476",
        "00026473",
        "00026467",
        "00026466",
        "00026317",
        "00026313"
    ],
    "00026296": [
        "00026463",
        "00026462",
        "00026461",
        "00026464",
        "00026332",
        "00026346",
        "00026347",
        "00026348",
        "00026457",
        "00026458",
        "00026369",
        "00026371",
        "00026373",
        "00026338",
        "00026341",
        "00026342",
        "00026380",
        "00026344",
        "00026351",
        "00026358",
        "00026381",
        "00026397",
        "00026430"
    ],
    "00026303": [
        "00026324",
        "00026478"
    ],
    "00026305": [
        "00026314"
    ],
    "00026306": [
        "00026451"
    ],
    "00026307": [
        "00026334",
        "00026336",
        "00026349",
        "00026352",
        "00026356",
        "00026333",
        "00026350",
        "00026452",
        "00026459",
        "00026343",
        "00026335",
        "00026322",
        "00026398",
        "00026429",
        "00026427",
        "00026424",
        "00026418"
    ],
    "00026309": [
        "00026315",
        "00026318"
    ],
    "00026311": [
        "00026304"
    ],
    "00026384": [
        "00026383",
        "00026294"
    ],
    "00026755": [
        "00026305",
        "00026306",
        "00026309",
        "00026311"
    ],
    "162416": [
        "00026299",
        "00026385",
        "00026295",
        "00026307",
        "00026296",
        "00026384",
        "00026388",
        "00026276",
        "00026755"
    ],
    "938743": [
        "00026300"
    ],
    "NO_MANAGER_LISTED": [
        "00026419",
        "00026376",
        "00026377",
        "00026386",
        "00026414",
        "00026415",
        "00026416",
        "00026425",
        "00026420",
        "00026421",
        "00026303",
        "00026302",
        "00026374",
        "00026323",
        "00026275"
    ]
}

from django.contrib.contenttypes.models import ContentType
from employee.models import *
from core.models import Workflow
from leave.models import Leave
from core.models import User

ct = ContentType.objects.get_for_model(Leave)
errors = []

for manager, matricules in data.items():
    try:
        manager = Employee.objects.get(registration_number=manager)
        user = User.objects.get(email=manager.email)

        obj, created = Workflow.objects.get_or_create(**{
            "name": f"Workflow approval conge for manager {manager.name}",
            "content_type": ct,
            "condition": f"obj.employee.registration_number in {str(matricules)}",
            "sub_organization": "SICPA"
        })

        if not created: continue
        obj.users.add(user)
        obj.save()
        print(f"Done for {manager}")
    except Exception as ex:
        errors.append(manager)
        print(f"Failed for {manager}")
from core.utils import set_schema

set_schema("kazi")

import pandas as pd

# ----------------------------------------------------------------------
# STEP 1: Load your data into a DataFrame
data_types = {
    'ID Système': str,
    'Person ID': str,  # Read as float to handle any decimal inputs
}
file_path = "/Users/tabaro/Desktop/payslip/manager-line.xlsx"

#
# Replace this line with the actual code to load your data. 
# Example if your data was in a CSV:
df = pd.read_excel(file_path, dtype=data_types)
#
# Since your data is an image, you must load it into a DataFrame named 'df'
# manually or using an OCR tool before running the rest of the code.
#
# ASSUMPTION: The DataFrame 'df' is loaded and contains the columns: 
#             'ID System' and 'Person ID'.
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# STEP 2: Group the DataFrame and aggregate 'Person ID' into a list
# ----------------------------------------------------------------------


# Group by the 'ID System' column and aggregate the 'Person ID' values into a list
# 'list' is a valid aggregation function in pandas
grouped_data = df.groupby('ID Système')['Person ID'].apply(list)

# ----------------------------------------------------------------------
# STEP 3: Convert the resulting pandas Series (grouped_data) into a Python dictionary
# ----------------------------------------------------------------------

data = grouped_data.to_dict()


# ----------------------------------------------------------------------
# STEP 4: Print the resulting dictionary (Optional)
# ----------------------------------------------------------------------
# print(system_person_id_dict)


from django.contrib.contenttypes.models import ContentType
from employee.models import *
from core.models import Workflow
from leave.models import Leave
from core.models import User

ct = ContentType.objects.get_for_model(Leave)
employees = Employee.objects.filter(
    registration_number__in=data.keys()
)
errors = []
print(data.keys())

for manager in employees:
    try:
        user = User.objects.get(email=manager.email)
        matricules = data.get(manager.registration_number, [])

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
        print(ex)
        errors.append(manager)
        print(f"Failed for {manager}")
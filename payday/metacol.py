from employee.models import *
from core.tasks import *

class CreatedBy:
    def __init__(self):
        self.id = 12

created_by = CreatedBy()

class MetaCol:
    def __init__(self):
        self.document = "/Users/tabaro/Desktop/grades.xlsx"
        self.created_by = created_by

meta_col = MetaCol()

model = Grade
fields = get_model_fields(model)
value = process_excel_file(meta_col, fields)

print(value)
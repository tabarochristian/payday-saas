"""
import pandas as pd

# Load the Excel file (adjust the filename as needed)
df1 = pd.read_excel('/Users/tabaro/Desktop/kazi/agents.xlsx')
df2 = pd.read_excel('/Users/tabaro/Desktop/kazi/agents-plus.xlsx')
df3 = pd.read_excel(
    '/Users/tabaro/Desktop/kazi/agents-plus-2.xlsx',
    dtype={"Compte": str}
)
df4 = pd.read_excel(
    '/Users/tabaro/Desktop/kazi/agents-plus-3.xlsx',
    dtype={"Employee ID": str}
)

# Standardize column names
df1.columns = [col.strip().lower() for col in df1.columns]
df2.columns = [col.strip().lower() for col in df2.columns]
df3.columns = [col.strip().lower() for col in df3.columns]
df4.columns = [col.strip().lower() for col in df4.columns]

# Normalize column names: strip and lowercase
df1.columns = [col.strip().lower() for col in df1.columns]
df2.columns = [col.strip().lower() for col in df2.columns]
df3.columns = [col.strip().lower() for col in df3.columns]
df4.columns = [col.strip().lower() for col in df4.columns]

# Function to generate a consistent name key (for merging)
def generate_name_key(name):
    return " ".join(sorted(name.strip().lower().split()))

# Apply name key to both tables
df1["name_key"] = df1["noms complet"].apply(generate_name_key)
df2["name_key"] = df2["noms complet"].apply(generate_name_key)
df3["name_key"] = df3["noms complet"].apply(generate_name_key)
df4["name_key"] = df4["noms complet"].apply(generate_name_key)

# Merge on the generated name key
# Merge df1 and df2 first
merged_df = pd.merge(df1, df2, on="name_key", how="left", suffixes=("_df1", "_df2"))

# Then merge the result with df3
merged_df = pd.merge(merged_df, df3, on="name_key", how="left")

# Then merge the result with df4
merged_df = pd.merge(merged_df, df4, on="name_key", how="left")

# Reconstruct final_name: Last Middle First from df1’s original name column
def reconstruct_final_name(name):
    parts = name.strip().lower().split()
    if len(parts) == 1:
        return parts[0]
    elif len(parts) == 2:
        return f"{parts[-1]} {parts[0]}"
    else:
        return f"{parts[-1]} {' '.join(parts[1:-1])} {parts[0]}"

# Normalize column names
merged_df.columns = [col.strip().lower() for col in merged_df.columns]

# Split full name into components
def split_name_parts(name):
    parts = name.strip().lower().split()
    if len(parts) == 1:
        return parts[0], "", ""
    elif len(parts) == 2:
        return parts[1], "", parts[0]
    else:
        return parts[-1], " ".join(parts[1:-1]), parts[0]

# designation: fonction in lowercase + salaire de base
designation_map = {
    item["name"].lower(): item["id"]
    for item in [
        {'id': 119, 'name': 'warehouseman-300.0'}, {'id': 120, 'name': 'warehouseman-150.0'},
        {'id': 122, 'name': 'opérateur de maintenance-150.0'}, {'id': 123, 'name': 'cleaning service-216.5'},
        {'id': 125, 'name': 'cleaning service-150.0'}, {'id': 126, 'name': 'cleaning service dga-400.0'},
        {'id': 128, 'name': 'hr generalist-1600.0'}, {'id': 129, 'name': 'chargée de communication-1600.0'},
        {'id': 130, 'name': 'general manager-8500.0'}, {'id': 131, 'name': 'supply chain manager-1600.0'},
        {'id': 132, 'name': 'driver-598.0'}, {'id': 133, 'name': 'driver-750.0'}, {'id': 134, 'name': 'driver-580.0'},
        {'id': 136, 'name': 'driver-450.0'}, {'id': 142, 'name': 'bi analyst-1485.0'},
        {'id': 143, 'name': 'finance assistant-1200.0'}, {'id': 144, 'name': 'office assistant-900.0'},
        {'id': 145, 'name': 'administration assistant-1350.0'}, {'id': 146, 'name': 'procurment import specialist-1350.0'},
        {'id': 147, 'name': 'procurment assistant-900.0'}, {'id': 148, 'name': 'storekeeper-1350.0'},
        {'id': 151, 'name': 'assistant storekeeper-750.0'}, {'id': 152, 'name': 'assistant storekeeper-900.0'},
        {'id': 153, 'name': 'opérateur de maintenance-1200.0'}, {'id': 158, 'name': 'it system admin & app support senior engineer-1600.0'},
        {'id': 159, 'name': 'it network engineer-1400.0'}, {'id': 160, 'name': 'it office technician-900.0'},
        {'id': 161, 'name': 'service center team leader-1524.0'}, {'id': 162, 'name': 'qhse officer-1350.0'},
        {'id': 163, 'name': 'service center technician-1200.0'}, {'id': 166, 'name': 'fst-750.0'},
        {'id': 168, 'name': 'maintenance specialist-900.0'}, {'id': 170, 'name': 'fst-900.0'},
        {'id': 178, 'name': 'opérateur maintenance-900.0'}, {'id': 200, 'name': 'team leader equipement & maintenance-1400.0'},
        {'id': 203, 'name': 'fst-1200.0'}, {'id': 205, 'name': 'operateur maintenance-900.0'},
        {'id': 208, 'name': 'fst-0.0'}, {'id': 226, 'name': 'fst site leader-1255.0'},
        {'id': 227, 'name': 'fst site leader-1300.0'}, {'id': 229, 'name': 'fst-1350.0'},
        {'id': 230, 'name': 'facilities engineer-1200.0'}, {'id': 235, 'name': 'hr assistant-900.0'}
    ]
}

branch_map = {
    item["name"].upper(): item["id"]
    for item in [
        {"id": 3, "name": "GOMA"},
        {"id": 4, "name": "LUBUMBASHI"},
        {"id": 5, "name": "KISANGANI"},
        {"id": 6, "name": "KINSHASA"}
    ]
}

# Extract first, middle, last names
merged_df[["first_name", "middle_name", "last_name"]] = merged_df["noms complet_df1"].apply(lambda x: pd.Series(split_name_parts(x)))

# Build designation: fonction in lowercase + salaire de base
merged_df["branch_id"] = merged_df["localisation"].fillna("").apply(lambda x: branch_map.get(x.strip().upper(), None)).astype("Int64")
merged_df["designation_str"] = merged_df["fonction_df1"].str.strip().str.lower() + "-" + merged_df["salaire de base"].astype(str)
merged_df["designation_id"] = merged_df["designation_str"].map(designation_map).astype("Int64")

# Normalize sex values
merged_df["gender"] = merged_df["sexe_x"].apply(lambda x: "FEMALE" if str(x).strip().upper() == "F" else "MALE")

# Parse date_of_join
# Parse date and keep only the date part
# Convert Excel serial date to proper datetime.date
merged_df["date_of_join"] = pd.to_datetime(
    merged_df["date d'embauche"], unit="D", origin="1899-12-30", errors="coerce"
).dt.date

# Format branch values
merged_df["branch"] = merged_df["localisation"].fillna("").apply(lambda x: x.strip().upper())
merged_df = merged_df.dropna(subset=["designation_id"])

# Extract only the required columns
final_df = merged_df[[
    "first_name", "middle_name", "last_name", "compte", "banque",
    "designation_id", "gender", "date_of_join", "branch_id", "employee id"
]]

import random

# Step 1: Cast to string safely
final_df["registration_number"] = final_df["employee id"].astype(str).str.strip()

# Step 2: Replace 'nan', empty, or invalid with a random string number
def clean_or_random(value):
    if not value or value.lower() == "nan":
        return str(random.randint(100000, 999999))  # 6-digit random string
    return value

final_df["registration_number"] = final_df["registration_number"].apply(clean_or_random)


final_df["payment_account"] = final_df["compte"]
final_df["payer_name"] = final_df["banque"]
final_df["marital_status"] = "SINGLE"
final_df["payment_method"] = "BANK"

# drop compte and banque
final_df = final_df.drop(columns=["compte", "banque", "employee id"])

# Replace empty strings with NaN
final_df.replace("", pd.NA, inplace=True)

# Convert all NaN/NA values to None
final_df = final_df.where(pd.notnull(final_df), None)

# Display or export final result
final_df.to_excel("agents_clean_table.xlsx", index=False)
final_df.to_json("agents_clean_table.json", orient="records")

print(final_df.to_dict(orient="records")[2])

for obj in final_df.to_dict(orient="records"):
    print(obj, "\n")

from employee.models import *
from core.utils import set_schema

set_schema("kazi")

Employee.objects.all().delete()
data = [Employee(**row) for row in final_df.to_dict(orient="records")]
Employee.objects.bulk_create(data)
"""



from difflib import SequenceMatcher
from core.utils import set_schema
from employee.models import *
import pandas as pd

set_schema("kazi")

# Step 1: Load Excel file
df = pd.read_excel("/Users/tabaro/Desktop/kazi/salaire.xlsx")
df.columns = [col.strip().lower() for col in df.columns]
print(df.columns)
df["nom_complets"] = df["nom complets"].astype(str).str.strip().str.lower()

# Step 2: Preprocess full name into tokens
def tokenize(name):
    return set(name.split())

df["name_tokens"] = df["nom_complets"].apply(tokenize)

# Step 3: Build lookup of Django employees with token sets
employee_cache = []
for emp in Employee.objects.all():
    parts = [emp.first_name, emp.middle_name, emp.last_name]
    tokens = set(filter(None, [p.strip().lower() for p in parts if p]))
    employee_cache.append({
        "instance": emp,
        "tokens": tokens
    })

# Step 4: Match and assign
for _, row in df.iterrows():
    excel_tokens = row["name_tokens"]
    best_match = None
    highest_score = 0

    for entry in employee_cache:
        overlap = excel_tokens & entry["tokens"]
        score = len(overlap)

        if score > highest_score:
            highest_score = score
            best_match = entry["instance"]

    # Step 5: Assign net if a match is found
    if best_match:
        metadata = {"net": row["net"]}
        best_match._metadata = metadata
        best_match.save()
        print(f"Matched: {row['nom_complets']} → {best_match.first_name} {best_match.last_name} | Net: {row['net']}")
    else:
        print(f"No match for: {row['nom_complets']}")


import pandas as pd

# Load the Excel file (adjust the filename as needed)
file_path = '/Users/tabaro/Downloads/grades (1).xlsx'
df = pd.read_excel(file_path)

# Strip whitespace and convert column names to lowercase
df.columns = [col.strip().lower() for col in df.columns]

# Concatenate 'nom' with 'metadata.salaire de base' into a new column
df["nom"] = df["nom"].str.strip().str.lower()
df["nom"] = df["nom"] + "-" + df["metadata.salaire de base"].astype(str)

# Display the result
print(df)

# Optional: save to a new Excel file
df.to_excel("processed_output.xlsx", index=False)

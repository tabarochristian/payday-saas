from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import F
import pandas as pd

# --- Django Imports ---
from core.utils import set_schema
from employee.models import Employee
from leave.models import Leave, TypeOfLeave, Status


# --- Configuration ---
# 1. Replace with your actual file path.
FILE_PATH = '/Users/tabaro/Downloads/agents_conges (1).xlsx'
SCHEMA_NAME = "kazi"
LEAVE_TYPE_NAME = "annuel" # Name of the TypeOfLeave to update

# Define the data types for robust Excel reading
DATA_TYPES = {
    'REGISTRATION_NUMBER': str,
    'SOLDE_CONGE': float,  # Read as float to handle any decimal inputs
}

# ----------------------------------------------------------------------
# PART 1: PANDAS DATA PROCESSING
# ----------------------------------------------------------------------

def get_employee_balances(file_path, data_types):
    """
    Reads the Excel file, ensures unique registration numbers are grouped,
    and extracts the SOLDE_CONGE value.
    Returns a dictionary mapping registration_number to its SOLDE_CONGE value.
    """
    try:
        df = pd.read_excel(file_path, dtype=data_types)

        # 1. CLEANING AND DEDUPING:
        # Convert REGISTRATION_NUMBER to string and drop rows where the key is missing/empty
        df['REGISTRATION_NUMBER'] = df['REGISTRATION_NUMBER'].astype(str).str.strip().replace('', pd.NA)
        df.dropna(subset=['REGISTRATION_NUMBER'], inplace=True)
        
        # 2. SELECT THE DESIRED COLUMNS:
        # We only need the key and the balance column.
        df = df[['REGISTRATION_NUMBER', 'SOLDE_CONGE']]

        # 3. HANDLE DUPLICATE REGISTRATION NUMBERS:
        # If there are duplicates, we need a policy (e.g., take the first one or average them).
        # We'll take the LAST entry for simplicity, assuming it's the most recent.
        df.drop_duplicates(subset=['REGISTRATION_NUMBER'], keep='last', inplace=True)

        # 4. FINAL CONVERSION:
        # Map REGISTRATION_NUMBER to SOLDE_CONGE (converted to a safe integer)
        balance_map = df.set_index('REGISTRATION_NUMBER')['SOLDE_CONGE'].round().astype(int).to_dict()
        
        print(f"Loaded {len(balance_map)} unique employee balances from Excel.")
        return balance_map

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found. Please check the path.")
        return {}
    except KeyError as e:
        print(f"Error: The required column {e} was not found in the Excel file. Please check column headers.")
        return {}
    except Exception as e:
        print(f"An unexpected error occurred during file processing: {e}")
        return {}


# ----------------------------------------------------------------------
# PART 2: DJANGO DATABASE UPDATE LOGIC
# ----------------------------------------------------------------------

@transaction.atomic
def update_employee_leave_balances(balance_map):
    """
    Updates the maximum leave duration allowed for employees based on the imported balance.
    NOTE: This assumes that you have a field on the Employee model (e.g., 'annual_leave_balance')
    or a dedicated LeaveBalance model. 
    
    Since a dedicated model isn't clear, we'll implement the logic that makes the most sense
    for a one-time initial load: updating the total allowed leave (max_duration) 
    in the Employee table or creating a pseudo-leave record.
    
    ***WARNING: CREATING A 'Leave' RECORD IS NOT THE CORRECT WAY TO SET A BALANCE.***
    The code below attempts to create a dummy record to reflect the balance, 
    but this is generally discouraged. The best solution is updating a dedicated balance field.
    """
    
    # Check if there are any balances to process
    if not balance_map:
        return

    # 1. Set the database schema
    set_schema(SCHEMA_NAME)
    
    try:
        # Find the specific TypeOfLeave
        try:
            leave_type = TypeOfLeave.objects.get(name__icontains=LEAVE_TYPE_NAME)
        except TypeOfLeave.DoesNotExist:
            print(f"Error: TypeOfLeave with name containing '{LEAVE_TYPE_NAME}' not found.")
            return

        # 2. Get all relevant employees in one query
        reg_numbers = balance_map.keys()
        employees = Employee.objects.filter(
            registration_number__in=reg_numbers
        )#.in_bulk(field_name='registration_number') # Get a dictionary mapped by reg_number

        leaves_to_create = []
        employees_found_count = 0
        
        # 3. Iterate over the found employees and prepare the data
        for employee in employees:
            reg_number = employee.registration_number
            SOLDE_CONGE = int(round(balance_map.get(reg_number)))
            
            # Filter out employees without a valid balance
            if SOLDE_CONGE is None: #or SOLDE_CONGE <= 0:
                continue

            employees_found_count += 1
            
            # *****************************************************************
            # CRITICAL LOGIC FIX:
            # We are creating a DUMMY "Leave Taken" record that spans the period 
            # *already taken* or used up to consume the total max duration, 
            # leaving the actual SOLDE_CONGE remaining.
            #
            # If max_duration is 30 days and SOLDE_CONGE is 10 days, then 20 days were "taken".
            # *****************************************************************
            
            taken_days = SOLDE_CONGE if SOLDE_CONGE < 0 else leave_type.max_duration - SOLDE_CONGE
            
            # Only create a record if some leave has been "taken" (to set the balance)
            # if taken_days > 0:
            # Use a dummy start date (e.g., Jan 1st of the current year)
            # and calculate the end date based on the *taken_days*.
            start_date = datetime(datetime.now().year, 1, 1).date()
            end_date = start_date + timedelta(days=taken_days) # - timedelta(days=1)
            
            leaves_to_create.append(Leave(
                employee=employee,
                type_of_leave=leave_type,
                reason="Initial leave consumption to reflect Solde Congé balance.",
                start_date=start_date,
                end_date=end_date,
                duration=taken_days, # Explicitly set duration for consistency
                status=Status.APPROVED,
                sub_organization='SICPA'
            ))

        # 4. Bulk Create the Dummy Leave Records
        if leaves_to_create:
            Leave.objects.bulk_create(leaves_to_create)
            print(f"Successfully created {len(leaves_to_create)} dummy 'taken' leave records.")
        else:
            print("No new leave records needed (all employees have full or zero balances).")

        print(f"Processed {employees_found_count} employees who had a balance.")

    except Exception as e:
        print(f"Database operation failed: {e}")
        # The @transaction.atomic decorator handles rollback on error

# ----------------------------------------------------------------------
# SCRIPT EXECUTION
# ----------------------------------------------------------------------

employee_balance_map = get_employee_balances(FILE_PATH, DATA_TYPES)

# Execute the database update
if employee_balance_map:
    update_employee_leave_balances(employee_balance_map)
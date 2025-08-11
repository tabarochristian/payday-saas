import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.http import HttpResponse
from django.contrib import messages
from django.apps import apps

from core.views import Exporter
from io import BytesIO
import pandas as pd

logger = logging.getLogger(__name__)  # Add logger for production logging

def safe_numeric(fn):
    def wrapper(df):
        try:
            result = fn(df)
            return result.astype('float64').fillna(0)
        except Exception:
            return pd.Series([0] * len(df), index=df.index, dtype='float64')
    return wrapper

class PayrollExporter(Exporter):  # Add mixins for security
    permission_required = ('payroll.view_payroll',)  # Example permission; adjust as needed
    action = ["view"]
    template_name = "exporter.html"

    # Configurable class attributes
    EXCLUDED_FIELDS = {
        "sub_organization", "created_by", "updated_by",
        "created_at", "updated_at", "_metadata", "id",
        "user", "create_user_on_save", "itempaid"
    }
    AGGREGATION_FIELDS = [
        'social_security_amount', 'amount_qp_employee',
        'amount_qp_employer', 'taxable_amount'
    ]
    COMPUTED_COLUMNS = {
        'absence': safe_numeric(lambda df: df['employee__working_days_per_month'].fillna(0)
            - df['employee__attendance'].fillna(0)),

        'dependants': safe_numeric(lambda df: df['employee__employee__marital_status'].eq('MARRIED').astype(int).fillna(0)
            + df['employee__children'].fillna(0).astype(int))
    }

    @property
    def model_class(self):
        """Return the Payroll model."""
        return apps.get_model('payroll', 'payroll')

    @property
    def models(self):
        """Cache frequently accessed models."""
        if not hasattr(self, "_models_cache"):
            self._models_cache = {
                'Payroll': self.model_class,
                'PaidEmployee': apps.get_model('payroll', 'paidemployee'),
                'Employee': apps.get_model('employee', 'employee'),
                'ItemPaid': apps.get_model('payroll', 'itempaid')
            }
        return self._models_cache

    def _get_object(self):
        """Return the Payroll instance or 404."""
        obj = get_object_or_404(
            self.models['Payroll'],
            pk=self.kwargs.get('pk')
        )
        return obj

    def list_of_items(self):
        payroll_obj = self._get_object()
        PaidEmployee = self.models['PaidEmployee']
        Employee = self.models['Employee']
        ItemPaid = self.models['ItemPaid']

        # Base employee and paid employee fields
        base_fields = self._build_employee_fields(Employee)
        base_fields.update(self._build_paid_employee_fields(PaidEmployee, Employee, base_fields))
        base_fields.update({
            'absence': 'absence',
            'dependants': 'dependants'
        })

        # Distinct ItemPaid names
        item_fields = {
            name: name.lower()
            for name in ItemPaid.objects
                .filter(employee__payroll=payroll_obj)
                .values_list('name', flat=True)
                .distinct()
        }
        return {**base_fields, **item_fields}

    def _normalize_verbose(self, *parts):
        """Helper to normalize verbose names."""
        return " → ".join(p.strip().title() for p in parts)

    def _build_employee_fields(self, Employee):
        """Extract Employee fields and one level of related subfields."""
        fields_map = {}
        for field in Employee._meta.fields:
            if field.name in self.EXCLUDED_FIELDS:
                continue

            if not field.is_relation:
                fields_map[self._normalize_verbose("Employee", field.verbose_name)] = \
                    f"employee__employee__{field.name}"
            else:
                prefix = self._normalize_verbose("Employee", field.verbose_name)
                for sub_field in field.related_model._meta.fields:
                    if sub_field.name not in self.EXCLUDED_FIELDS:
                        fields_map[self._normalize_verbose(prefix, sub_field.verbose_name)] = \
                            f"employee__employee__{field.name}__{sub_field.name}"
        return fields_map

    def _build_paid_employee_fields(self, PaidEmployee, Employee, existing_fields):
        """Extract PaidEmployee fields excluding overlaps and relations."""
        normalized_existing = {name.lower() for name in existing_fields}
        employee_relations = {f.name for f in Employee._meta.fields if f.is_relation}
        employee_field_names = {f.name for f in Employee._meta.fields}

        field_map = {}
        for field in PaidEmployee._meta.fields:
            if (
                field.name in employee_field_names
                or field.is_relation
                or field.name in self.EXCLUDED_FIELDS
                or field.name in employee_relations
            ):
                continue

            verbose = field.verbose_name.strip().title()
            if verbose.lower() in normalized_existing:
                continue
            field_map[verbose] = f'employee__{field.name.lower()}'

        # Nested Employee direct fields
        for field in Employee._meta.fields:
            if not field.is_relation and field.name not in self.EXCLUDED_FIELDS:
                verbose = self._normalize_verbose("Employee", field.verbose_name)
                if verbose.lower() not in normalized_existing:
                    field_map[verbose] = f'employee__{field.name.lower()}'

        return field_map

    def apply_computed_columns(self, df: pd.DataFrame, computations: dict) -> pd.DataFrame:
        """Apply computed columns safely."""
        for col_name, func in computations.items():
            try:
                result = func(df)
                if not isinstance(result, pd.Series):
                    raise TypeError(f"Computation for '{col_name}' must return a Series.")
                df[col_name] = result
            except Exception as e:
                logger.warning(f"Failed to compute '{col_name}': {e}")  # Use logger
                df[col_name] = None
        return df

    def get_verbose_path_map(self, model, df: pd.DataFrame) -> dict:
        """Map field paths to verbose breadcrumb names."""
        verbose_map = {}
        for col in df.columns:
            parts = col.split('__')
            current_model = model
            path_labels = []
            for i, part in enumerate(parts):
                try:
                    field = current_model._meta.get_field(part)
                except Exception:
                    path_labels = []
                    break
                path_labels.append(field.verbose_name.title())
                if field.is_relation:
                    current_model = field.related_model
                elif i < len(parts) - 1:
                    path_labels = []
                    break
            if path_labels:
                verbose_map[col] = " → ".join(path_labels)
        return verbose_map

    def _aggregate_and_pivot(self, df_raw, field_paths, item_names):
        """Aggregate payroll data and pivot items into columns by 'name'."""
        try:
            # Identify fields that vary (identity fields)
            identity_fields = [
                col for col in field_paths
                if col.startswith('employee__') and df_raw[col].dropna().nunique() > 1
            ]
            group_keys = [k for k in identity_fields + ['name'] if k in df_raw.columns]

            # Group while keeping 'name' as a regular column
            df_grouped = (
                df_raw
                .groupby(group_keys, as_index=False)
                .agg({f: 'sum' for f in self.AGGREGATION_FIELDS})
            )

            # Compute unified 'amount'
            df_grouped['amount'] = df_grouped['amount_qp_employee'].where(
                df_grouped['amount_qp_employee'].ne(0) & df_grouped['amount_qp_employee'].notna(),
                df_grouped['amount_qp_employer']
            )

            # Ensure 'name' exists and is treated as column
            if 'name' not in df_grouped.columns:
                raise ValueError("'name' column missing before pivot — check group_keys.")

            # Pivot so each distinct item name becomes its own column with amount values
            df_grouped['name'] = df_grouped['name'].str.lower()
            pivot_index = [k for k in group_keys if k != 'name']
            df_pivot = (
                df_grouped
                .pivot(index=pivot_index, columns='name', values='amount')
                .fillna(0)
                .reset_index()
            )

            # Flatten MultiIndex columns after pivot (in case of any)
            df_pivot.columns = [
                col if not isinstance(col, tuple) else col[-1]
                for col in df_pivot.columns
            ]

            # Reattach removed fields if they are consistent within each group
            removed_fields = [
                col for col in field_paths
                if col.startswith('employee__')
                and col in df_raw.columns
                and col not in identity_fields
            ]
            for field in removed_fields:
                consistency = df_raw.groupby(pivot_index)[field].nunique(dropna=False)
                if consistency.max() == 1:
                    field_values = df_raw.groupby(pivot_index)[field].first().reset_index()
                    df_pivot = df_pivot.merge(field_values, on=pivot_index, how='left')
                else:
                    logger.warning(f"Field '{field}' varies within groups and was not reattached.")

            return df_pivot, pivot_index
        except Exception as e:
            logger.error(f"Aggregation and pivot failed: {e}")
            raise

    def report(self, fields):
        payroll_obj = self._get_object()
        ItemPaid = self.models['ItemPaid']

        try:
            items_qs = ItemPaid.objects.filter(employee__payroll=payroll_obj).select_related(
                'employee', 'employee__employee'
            ).prefetch_related('employee__employee')  # Add prefetch for potential relations

            item_names = {name.lower() for name in items_qs.values_list('name', flat=True).distinct()}

            field_paths = [f for f in fields if f not in item_names]
            field_paths += [f.name for f in ItemPaid._meta.fields if f.name not in ['employee', '_metadata']]
            field_paths =  [field for field in list(set(field_paths)) if field.split('__')[0] in [_field.name for _field in ItemPaid._meta.fields]]
            

            df_raw = pd.DataFrame.from_records(items_qs.values(*field_paths))
            if df_raw.empty:
                raise ValueError("No data found for the selected payroll.")

            df_pivot, pivot_index = self._aggregate_and_pivot(df_raw, field_paths, item_names)

            df_pivot = self.apply_computed_columns(df_pivot, self.COMPUTED_COLUMNS)

            # Keep only selected fields
            df_pivot = df_pivot[[col for col in fields if col in df_pivot.columns]]

            # Rename to verbose names
            verbose_map = self.get_verbose_path_map(ItemPaid, df_pivot)
            df_pivot.rename(columns=verbose_map, inplace=True)
            df_pivot.columns = [col.title() for col in df_pivot.columns]

            # Add total row: Put 'Total' only in first non-numeric column if possible
            numeric_cols = df_pivot.select_dtypes(include='number').columns
            total_row = df_pivot[numeric_cols].sum(numeric_only=True)
            total_dict = total_row.to_dict()
            if df_pivot.columns[0] not in numeric_cols:  # Assume first col is identifier
                total_dict[df_pivot.columns[0]] = 'Total'
            for col in df_pivot.columns:
                if col not in total_dict:
                    total_dict[col] = ''
            df_pivot = pd.concat([df_pivot, pd.DataFrame([total_dict])], ignore_index=True)
            df_pivot[df_pivot.select_dtypes(include='number').columns] = df_pivot.select_dtypes(include='number').abs()
            return df_pivot.fillna('')
        except ValueError as e:
            logger.warning(f"Report generation warning: {e}")
            raise
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            raise

    def get(self, request, pk, app='payroll', model='payroll'):
        model_class = self.model_class
        list_of_items = self.list_of_items()
        return render(request, self.template_name, locals())

    def post(self, request, pk, app='payroll', model='payroll'):
        selected_items_order = request.POST.get('selected_items_order', '')
        if not selected_items_order:
            messages.error(request, "No fields selected for export.")
            return redirect(reverse_lazy('payroll:exporter', kwargs={'pk': pk}))  # Redirect on error

        fields = [f.strip() for f in selected_items_order.split(',') if f.strip()]
        # Validate fields against available ones
        available_fields = list(self.list_of_items().values())  # Assuming values are paths/names
        invalid_fields = [f for f in fields if f not in available_fields]
        if invalid_fields:
            messages.error(request, f"Invalid fields selected: {', '.join(invalid_fields)}")
            return redirect(reverse_lazy('payroll:exporter', kwargs={'pk': pk}))

        try:
            df = self.report(fields=fields)
            obj = self._get_object()

            # Create Excel file in memory
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Report')

                workbook = writer.book
                worksheet = writer.sheets['Report']

                # Define format for last row: bold + dark orange fill
                last_row_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#FF8C00',  # Dark orange
                    'font_color': 'white'   # Optional: white text for contrast
                })

                # Get last row index (0-based, plus header row)
                last_row_idx = len(df)

                # Get last row index and number of columns
                last_row_idx = len(df)
                num_cols = len(df.columns)

                # Apply format cell-by-cell across actual columns
                for col_idx in range(num_cols):
                    worksheet.write(last_row_idx, col_idx, df.iloc[-1, col_idx], last_row_format)

            output.seek(0)
            messages.success(request, "Exportation réussie.")

            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="payroll_{obj.name.lower()}.xlsx"'
            return response

        except Exception as e:
            messages.error(request, f"Export failed: {str(e)}")
            return redirect(reverse_lazy('payroll:exporter', kwargs={'pk': pk}))
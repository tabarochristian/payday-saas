from django.apps import apps
import inspect
from django.db.models import ForeignKey, ManyToManyField, OneToOneField

def get_field_type(field):
    field_class = field.__class__.__name__
    if isinstance(field, (ForeignKey, OneToOneField)):
        return f"-> {field.related_model.__name__}"
    elif isinstance(field, ManyToManyField):
        return f"[{field.related_model.__name__}]"
    return field_class

def get_model_tree(model, visited=None, depth=0):
    if visited is None:
        visited = set()

    indent = "  " * depth
    model_name = model.__name__
    verbose_name = model._meta.verbose_name.title()
    model_help = inspect.getdoc(model) or "No description available."

    output = [f"{indent}- **{model_name}** (_{verbose_name}_)"]
    output.append(f"{indent}  > {model_help}")

    for field in model._meta.fields + model._meta.many_to_many:
        field_name = field.name
        field_type = get_field_type(field)
        field_verbose = field.verbose_name.title()
        help_text = field.help_text or "No help text provided."
        output.append(f"{indent}  - `{field_name}` ({field_type}): {field_verbose} — {help_text}")

        # Dive deeper into related models
        if field.is_relation and hasattr(field, "related_model") and field.related_model not in visited:
            visited.add(field.related_model)
            output.append(get_model_tree(field.related_model, visited, depth + 1))

    return "\n".join(output)

def generate_readme():
    readme_lines = ["# 📘 Django Models Documentation\n"]
    models = apps.get_models()

    for model in models:
        if model._meta.app_label not in ["employee", "leave", "payroll"]:
            continue
        readme_lines.append(get_model_tree(model))
        readme_lines.append("\n---\n")

    with open("README.md", "w", encoding="utf-8") as f:
        f.write("\n".join(readme_lines))

    print("README.md generated successfully!")

# Run this in a Django context
generate_readme()

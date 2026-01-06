from rest_framework.serializers import ModelSerializer
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models import PointField


def model_serializer_factory(model, fields="__all__", depth=1):
    cls_name = f"{model.__name__}Serializer"

    def create(self, validated_data):
        for field in model._meta.get_fields():
            if isinstance(field, PointField):
                val = validated_data.get(field.name)
                if isinstance(val, dict) and val.get("type") == "Point":
                    coords = val.get("coordinates", [])
                    if len(coords) == 2:
                        # GeoJSON order is [lon, lat]
                        validated_data[field.name] = Point(coords[1], coords[0])
        return super(serializer_class, self).create(validated_data)

    def update(self, instance, validated_data):
        for field in model._meta.get_fields():
            if isinstance(field, PointField):
                val = validated_data.get(field.name)
                if isinstance(val, dict) and val.get("type") == "Point":
                    coords = val.get("coordinates", [])
                    if len(coords) == 2:
                        validated_data[field.name] = Point(coords[1], coords[0])
        return super(serializer_class, self).update(instance, validated_data)

    serializer_class = type(
        cls_name,
        (ModelSerializer,),
        {
            "Meta": type("Meta", (), {"model": model, "fields": fields, "depth": depth}),
            "create": create,
            "update": update,
        },
    )

    return serializer_class

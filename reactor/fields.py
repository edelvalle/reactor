from . import serializer

__all__ = ["Model", "QuerySet"]


class ModelLoader:
    def __getitem__(self, ModelClass):
        if not hasattr(ModelClass, "__get_validators__"):

            def validate(value, field):
                if not isinstance(value, ModelClass):
                    value = serializer.decode(value)
                return value

            def __get_validators__(cls):
                yield validate

            ModelClass.__get_validators__ = classmethod(__get_validators__)
        return ModelClass


class QuerySetLoader:
    def __getitem__(self, ModelClass):
        QSClass = ModelClass.objects._queryset_class
        if not hasattr(QSClass, "__get_validators__"):

            def validate(value, field):
                if not isinstance(value, QSClass):
                    return ModelClass.objects.filter(pk__in=value)
                return value

            def __get_validators__(cls):
                yield validate

            QSClass.__get_validators__ = classmethod(__get_validators__)

        return QSClass[ModelClass]


Model = ModelLoader()
QuerySet = QuerySetLoader()

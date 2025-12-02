from dataclasses import asdict

class SubscriptableMixin:
    """
    A mixin class that adds dictionary-style access (subscriptability)
    to any Python class, particularly useful for dataclasses.
    """
    def __getitem__(self, key):
        """
        Allows access via object[key]. Internally, it treats the object
        as a dictionary using dataclasses.asdict().
        """
        # asdict() converts the dataclass instance into a standard Python dict.
        # We then look up the key in that dictionary.
        try:
            return asdict(self)[key]
        except KeyError as e:
            raise KeyError(f"Key '{key}' not found in model.") from e

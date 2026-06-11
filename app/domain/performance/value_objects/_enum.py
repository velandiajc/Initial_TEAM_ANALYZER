from enum import Enum


class GovernedEnum(Enum):
    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value

        normalized = (
            str(value)
            .strip()
            .upper()
            .replace(" ", "_")
            .replace("-", "_")
        )
        for item in cls:
            if item.value == normalized or item.name == normalized:
                return item

        raise ValueError(f"Unsupported {cls.__name__}: {value}")

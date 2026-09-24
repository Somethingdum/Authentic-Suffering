"""Kernel exception types. Every validator failure names the rule id it enforces (L14)."""


class ASError(Exception):
    """Base class. ``rule`` is the rule id from docs/as/RULES.md that was violated."""

    rule: str = "UNSPECIFIED"

    def __init__(self, message: str, *, rule: str | None = None):
        super().__init__(message)
        if rule is not None:
            self.rule = rule


class StoreError(ASError):
    rule = "STORE-00"


class ScopeError(StoreError):
    """A module tried to write a table it does not own (STORE-02)."""

    rule = "STORE-02"


class SchemaError(StoreError):
    rule = "STORE-04"


class UnknownEventType(StoreError):
    rule = "STORE-05"


class ClockError(ASError):
    rule = "TIME-01"


class ValidationFailure(ASError):
    """Raised by gates G0..G12 inside a turn transaction; triggers rollback."""

    rule = "GATE-00"

    def __init__(self, message: str, *, rule: str, stage: int | None = None):
        super().__init__(message, rule=rule)
        self.stage = stage


class SettingsError(ASError):
    """A run setting, or a combination of settings, the world cannot honour (P10: WG-34)."""

    rule = "SET-00"

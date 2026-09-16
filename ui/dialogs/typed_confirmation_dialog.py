"""Pure typed-confirmation predicate used by dialog services and tests."""


def typed_value_matches(value: str, expected: str) -> bool:
    return value == expected

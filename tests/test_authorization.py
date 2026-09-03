import pytest

from app.authorization import ALL_CATEGORIES, ROLE_CATEGORIES, categories_for_role


@pytest.mark.parametrize(
    ("role", "categories"),
    [
        ("employee", ("general",)),
        ("hr", ("general", "hr")),
        ("finance", ("general", "finance")),
        ("engineering", ("general", "engineering")),
        ("marketing", ("general", "marketing")),
        ("admin", ALL_CATEGORIES),
    ],
)
def test_role_categories(role: str, categories: tuple[str, ...]) -> None:
    assert categories_for_role(role) == categories


def test_mapping_contains_only_supported_roles() -> None:
    assert set(ROLE_CATEGORIES) == {"employee", "hr", "finance", "engineering", "marketing", "admin"}


from typing import Literal

Role = Literal["employee", "hr", "finance", "engineering", "marketing", "admin"]
Category = Literal["general", "hr", "finance", "engineering", "marketing"]

ALL_CATEGORIES: tuple[Category, ...] = (
    "general",
    "hr",
    "finance",
    "engineering",
    "marketing",
)

ROLE_CATEGORIES: dict[Role, tuple[Category, ...]] = {
    "employee": ("general",),
    "hr": ("general", "hr"),
    "finance": ("general", "finance"),
    "engineering": ("general", "engineering"),
    "marketing": ("general", "marketing"),
    "admin": ALL_CATEGORIES,
}


def categories_for_role(role: str) -> tuple[Category, ...]:
    try:
        return ROLE_CATEGORIES[role]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError("Unknown role") from exc


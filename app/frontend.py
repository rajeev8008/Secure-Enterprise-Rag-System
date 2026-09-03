from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import get_current_user
from app.authorization import categories_for_role
from app.models import User

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/", response_class=RedirectResponse)
def home_page() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="login.html")


@router.get("/chat", response_class=HTMLResponse)
def chat_page(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={"user": user, "categories": categories_for_role(user.role)},
    )

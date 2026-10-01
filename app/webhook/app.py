"""Starlette app hosting the GitHub webhook endpoint."""

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.webhook.github import github_webhook


async def health(request):
    return JSONResponse({"status": "ok"})


def create_webhook_app() -> Starlette:
    return Starlette(routes=[
        Route("/webhook/github", github_webhook, methods=["POST"]),
        Route("/health", health, methods=["GET"]),
    ])

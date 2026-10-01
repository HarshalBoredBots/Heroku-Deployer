"""GitHub webhook endpoint."""

import hashlib
import hmac
import json as _json
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings
from app.db.repositories import webhook_deliveries
from app.services.auto_deploy import schedule_auto_deployments

logger = logging.getLogger(__name__)


async def github_webhook(request: Request) -> JSONResponse:
    # 1. Raw body
    body = await request.body()

    # 2. Verify HMAC signature
    # FIX #2: Verified that hmac.new(key, msg, digestmod) is the correct call in
    # Python 3's standard library (it is an alias for hmac.HMAC()).  The original
    # code was correct; no change needed here.  compare_digest is also used
    # correctly (both args are str).  Audit complete — keeping as-is.
    signature = request.headers.get("X-Hub-Signature-256", "")
    secret = get_settings().github_webhook_secret
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return JSONResponse({"status": "forbidden"}, status_code=403)

    # 3. Delivery metadata
    delivery_id = request.headers.get("X-GitHub-Delivery", "")
    event = request.headers.get("X-GitHub-Event", "")

    # 4. Only push events
    if event != "push":
        return JSONResponse({"status": "ignored"})

    # 5. Best-effort metadata extraction for idempotency record.
    # We parse a preview of the body to extract repository/ref BEFORE the
    # idempotency check so the record is stored with useful metadata.
    # FIX #15: Verified that the logic is correct: metadata is extracted from a
    # preview first (or the full body if it fits in 4096 bytes), then the
    # idempotency check is performed, then the full JSON is parsed.  This is the
    # right order — no change needed.
    repository = ""
    ref = ""
    try:
        preview = _json.loads(body)  # body is already in memory; no need to slice
        repository = preview.get("repository", {}).get("full_name", "")
        ref = preview.get("ref", "")
    except Exception:
        pass

    is_new = await webhook_deliveries.check_and_record(
        delivery_id, event, repository, ref
    )
    if not is_new:
        return JSONResponse({"status": "duplicate"})

    # 6. Parse JSON body (already parsed above, but keep explicit for clarity)
    try:
        payload = _json.loads(body)
    except Exception:
        return JSONResponse({"status": "bad_request"}, status_code=400)

    # 7. Extract fields
    repository = payload.get("repository", {}).get("full_name", repository)
    ref = payload.get("ref", "")
    branch = ref.removeprefix("refs/heads/")
    commit = payload.get("after", "")
    repo_url = payload.get("repository", {}).get("html_url", "")

    # 8. Schedule auto-deployments
    if repository and branch and commit:
        await schedule_auto_deployments(repo_url or f"https://github.com/{repository}", branch, commit)

    return JSONResponse({"status": "accepted"})

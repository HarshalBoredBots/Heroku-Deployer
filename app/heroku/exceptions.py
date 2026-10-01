"""Heroku API exception hierarchy."""


class HerokuAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class HerokuAuthError(HerokuAPIError): ...        # 401
class HerokuNotFoundError(HerokuAPIError): ...    # 404
class HerokuConflictError(HerokuAPIError): ...    # 409
class HerokuValidationError(HerokuAPIError): ...  # 422
class HerokuRateLimitError(HerokuAPIError): ...   # 429
class HerokuServerError(HerokuAPIError): ...      # 5xx

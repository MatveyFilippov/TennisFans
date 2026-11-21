from typing import Any


class Problem(Exception):
    def __init__(self, status: int, code: str, detail: str, **context: Any) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.context = context


def forbidden() -> Problem:
    return Problem(403, "forbidden", "You do not have permission to perform this action")


def missing() -> Problem:
    return Problem(404, "not_found", "The requested resource does not exist")


def conflict(code: str, detail: str, **context: Any) -> Problem:
    return Problem(409, code, detail, **context)


def invalid(code: str, detail: str) -> Problem:
    return Problem(422, code, detail)

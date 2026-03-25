"""
Structured error classes for shuati CLI.
"""


class ShuatiError(Exception):
    """Base exception with structured error code."""

    def __init__(self, message: str, code: str = "internal_error"):
        self.message = message
        self.code = code
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "ok": False,
            "schema_version": "1",
            "error": {
                "code": self.code,
                "message": self.message,
            },
        }


class NotAuthenticatedError(ShuatiError):
    def __init__(self, message: str = "未登录，请先运行 shuati login"):
        super().__init__(message, "not_authenticated")


class InvalidTokenError(ShuatiError):
    def __init__(self, message: str = "Token无效或已过期，请重新登录"):
        super().__init__(message, "invalid_token")


class SyncError(ShuatiError):
    def __init__(self, message: str):
        super().__init__(message, "sync_failed")


class NoDataError(ShuatiError):
    def __init__(self, message: str = "没有找到数据"):
        super().__init__(message, "no_data")


class GenerationError(ShuatiError):
    def __init__(self, message: str):
        super().__init__(message, "generation_failed")


class NetworkError(ShuatiError):
    def __init__(self, message: str = "网络请求失败"):
        super().__init__(message, "network_error")

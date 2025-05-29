class BehexException(Exception):
    """Base exception for the application"""
    pass


class AuthenticationError(BehexException):
    """Authentication related errors"""
    pass


class AuthorizationError(BehexException):
    """Authorization related errors"""
    pass


class ValidationError(BehexException):
    """Validation related errors"""
    pass


class NotFoundError(BehexException):
    """Resource not found errors"""
    pass


class ConflictError(BehexException):
    """Resource conflict errors"""
    pass


class FileOperationError(BehexException):
    """File operation related errors"""
    pass 
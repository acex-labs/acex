"""Common exceptions for ACE-X DevKit."""


class AcexDevkitException(Exception):
    """Base exception for ACE-X DevKit."""
    pass


class MethodNotImplemented(AcexDevkitException):
    """Raised when a required method is not implemented."""
    pass


class DriverException(AcexDevkitException):
    """Base exception for driver-related errors."""
    pass


class ConnectionError(DriverException):
    """Raised when device connection fails."""
    pass


class ConfigurationError(DriverException):
    """Raised when configuration application fails."""
    pass


class VerificationError(DriverException):
    """Raised when configuration verification fails."""
    pass


class RenderingError(DriverException):
    """Raised when configuration rendering fails."""
    pass


class ParsingError(DriverException):
    """Raised when configuration parsing fails."""
    pass

class AppError(Exception):
    """Base exception for Resume Intelligence Platform errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class ParserError(AppError):
    """Raised when document parsing fails (corrupted file, wrong type, empty, password protected)."""
    pass

class ValidationError(AppError):
    """Raised when data validations or contract assertions fail."""
    pass

class LLMError(AppError):
    """Raised when LLM API processing fails (timeouts, rate limits, format issues)."""
    pass

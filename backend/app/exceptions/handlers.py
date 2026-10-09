from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse

class OneDMSException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class NotFoundException(OneDMSException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, 404)

class ValidationException(OneDMSException):
    def __init__(self, message: str = "Validation error"):
        super().__init__(message, 422)

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(OneDMSException)
    async def onedms_exception_handler(request: Request, exc: OneDMSException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": exc.message},
        )

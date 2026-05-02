from dotenv import load_dotenv
import sys
from loguru import logger

load_dotenv()  # Load environment variables from .env file

# Configure loguru
logger.remove()
logger.add(sys.stderr, level="DEBUG", colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
logger.add("logs/backend.log", rotation="10 MB", retention="10 days", level="DEBUG")

# Intercept standard logging (basic integration)
import logging
class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())

logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]

from .routes import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

def get_logger(name: str) -> logging.Logger:

    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        fmt = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(fmt)
        
        # Derive project root: logger.py -> core -> copilot -> project_root
        _project_root = Path(__file__).resolve().parent.parent.parent
        _data_dir = _project_root / "data"
        _data_dir.mkdir(exist_ok=True)
        log_file = _data_dir / "copilot.log"
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
    return logger

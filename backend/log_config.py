import logging
from logging.config import dictConfig
import os
import sys

# --- Check for Debug File Logging ---
verbose_level_str = os.getenv('LOG_VERBOSE', '1')
try:
    verbose_level = int(verbose_level_str)
except ValueError:
    verbose_level = 1

LOG_TO_FILE = verbose_level >= 2
LOG_DIR = 'logs'
LOG_FILE = os.path.join(LOG_DIR, 'session.log')

if LOG_TO_FILE:
    # Ensure the logs directory exists
    os.makedirs(LOG_DIR, exist_ok=True)
    print(f"--- DETAILED LOGGING ENABLED. LOGS WILL BE SAVED TO: {os.path.abspath(LOG_FILE)} ---")


# --- Custom Verbosity Filter ---
class VerbosityFilter(logging.Filter):
    def __init__(self, name=''):
        super().__init__(name)
        self.min_level = logging.INFO

        if verbose_level == 0:
            self.min_level = logging.CRITICAL + 1
        elif verbose_level == 1:
            self.min_level = logging.INFO
        elif verbose_level >= 2:
            self.min_level = logging.DEBUG
        else:
            print(f"Log Filter: Invalid LOG_VERBOSE value '{verbose_level_str}'. Defaulting to level 1 (INFO).")

    def filter(self, record):
        return record.levelno >= self.min_level

log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "verbosity_filter": {
            "()": VerbosityFilter,
        }
    },
    "formatters": {
        "default": {
            # Use the standard Python formatter. This removes the hidden dependency on uvicorn
            # that causes issues with PyInstaller.
            "()": "logging.Formatter",
            "fmt": "%(asctime)s [%(levelname)-8s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "file_formatter": {
            "fmt": "%(asctime)s [%(levelname)-8s] in %(filename)s:%(lineno)d: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "filters": ["verbosity_filter"]
        },
    },
    "loggers": {
        "mvp_logger": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False
        },
        # We can simplify these as we are no longer using the uvicorn formatters
        "uvicorn.error": {
            "level": "INFO",
            "handlers": ["default"],
            "propagate": False,
        },
        "uvicorn.access": {
            "level": "INFO",
            "handlers": ["default"],
            "propagate": False,
        },
    },
}

# --- Add File Handler if in Debug Mode ---
if LOG_TO_FILE:
    log_config['handlers']['file_handler'] = {
        "class": "logging.FileHandler",
        "formatter": "file_formatter",
        "filename": LOG_FILE,
        "mode": "w",  # Overwrite the log file on each run
        "encoding": "utf-8",
    }
    # Add the file handler to all relevant loggers
    log_config['loggers']['mvp_logger']['handlers'].append('file_handler')
    log_config['loggers']['uvicorn.error']['handlers'].append('file_handler')
    log_config['loggers']['uvicorn.access']['handlers'].append('file_handler')


# Apply config and get the main logger instance
dictConfig(log_config)
logger = logging.getLogger('mvp_logger')

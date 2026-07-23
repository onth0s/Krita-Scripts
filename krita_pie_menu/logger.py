import os
import time
import traceback
from typing import Optional

LOG_FILE_PATH = os.path.join(
    os.environ.get('APPDATA', os.path.expanduser('~')),
    'krita',
    'pykrita',
    'krita_scripts.log'
)
MAX_LOG_BYTES = 500 * 1024  # 500 KB

def _rotate_if_needed():
    if os.path.exists(LOG_FILE_PATH):
        try:
            if os.path.getsize(LOG_FILE_PATH) > MAX_LOG_BYTES:
                old_log = LOG_FILE_PATH + ".old"
                if os.path.exists(old_log):
                    os.remove(old_log)
                os.rename(LOG_FILE_PATH, old_log)
        except Exception:
            pass

def log_message(level: str, module: str, message: str, exception: Optional[BaseException] = None):
    try:
        _rotate_if_needed()
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] [{level.upper()}] [{module}] {message}\n"
        if exception:
            exc_fmt = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
            log_line += f"Exception trace:\n{exc_fmt}\n"

        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
        with open(LOG_FILE_PATH, 'a', encoding='utf-8') as f:
            f.write(log_line)
    except Exception:
        pass

def log_info(module: str, message: str):
    log_message("INFO", module, message)

def log_warning(module: str, message: str):
    log_message("WARNING", module, message)

def log_error(module: str, message: str, exception: Optional[BaseException] = None):
    log_message("ERROR", module, message, exception)

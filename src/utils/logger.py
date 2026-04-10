import logging
import colorlog
import sys

class AppLogger:
    def __init__(self, name="KisanBot"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            handler = colorlog.StreamHandler(sys.stdout)
            # Format: [Date Time] LEVEL TraceID Message
            formatter = colorlog.ColoredFormatter(
                "%(white)s[%(asctime)s] %(log_color)s%(levelname)-8s %(blue)s%(message)s",
                datefmt="%d/%m/%y %H:%M:%S",
                log_colors={
                    'DEBUG':    'cyan',
                    'INFO':     'green',
                    'WARNING':  'yellow',
                    'ERROR':    'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def info(self, msg, session_id=""):
        trace = f"{session_id} " if session_id else ""
        self.logger.info(f"{trace}{msg}")

    def error(self, msg, session_id=""):
        trace = f"{session_id} " if session_id else ""
        self.logger.error(f"{trace}{msg}")

    def warning(self, msg, session_id=""):
        trace = f"{session_id} " if session_id else ""
        self.logger.warning(f"{trace}{msg}")

    def user_message(self, msg, session_id=""):
        trace = f"{session_id} " if session_id else ""
        # Cyan label for user input visibility in terminal
        self.logger.info(f"{trace}\033[96mUser Message:\033[0m {msg}")

    def assistant_message(self, msg, session_id=""):
        trace = f"{session_id} " if session_id else ""
        # Magenta label for assistant response visibility in terminal
        self.logger.info(f"{trace}\033[95mAssistant:\033[0m {msg}")

# Global instance
logger = AppLogger()

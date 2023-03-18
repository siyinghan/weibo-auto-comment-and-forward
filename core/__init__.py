# create "log" folder if it is not exist
import logging
import os
import sys

from termcolor import colored

os.makedirs("log", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(processName)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("./log/weibo-auto.log"),
        logging.StreamHandler(stream=sys.stdout)
    ]
)


class ColorFilter(logging.Filter):
    """
    Define a custom filter to color warnings and errors.
    """

    def filter(self, record):
        """
        Filter method for the logging handler to color messages based on their log level.
        :param record: The log record to process.
        :type record: logging.LogRecord
        :return: A boolean indicating whether the log record should be processed or not.
        :rtype: bool
        """
        if record.levelno == logging.WARNING:
            record.msg = colored(record.msg, 'yellow')
        elif record.levelno == logging.ERROR:
            record.msg = colored(record.msg, 'red')
        return True


color_filter = ColorFilter()
logger_comment_sender = logging.getLogger("CS")
logger_comment_sender.addFilter(color_filter)

weibo_login_url = "https://weibo.com/login.php"

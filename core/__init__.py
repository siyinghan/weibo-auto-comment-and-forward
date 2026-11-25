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

from config import (
    CHAOHUA_NAMES, CHAOHUA_POST_LINK, CHAOHUA_POST_TIMES, CHAOHUA_PRE_POST_TEXT,
    CHAOHUA_SWITCH_DELAY, CHAOHUA_SYNC_TO_WEIBO, CHAOHUA_URLS,
    COMMENT_FORWARD_SWITCH_DELAY, COMMENTS_PER_ACCOUNT, FORWARDS_PER_ACCOUNT,
    SIGNIN_CHAOHUA_URLS,
)

weibo_login_url = "https://weibo.com/login.php"

# Backward-compatible names used by the task modules.  The real settings live
# in config.py at the project root.
pre_post_text = CHAOHUA_PRE_POST_TEXT
post_link = CHAOHUA_POST_LINK
chaohua_urls = list(CHAOHUA_URLS)
chaohua_names = dict(CHAOHUA_NAMES)
signin_chaohua_urls = list(SIGNIN_CHAOHUA_URLS)
comments_per_account = COMMENTS_PER_ACCOUNT
forwards_per_account = FORWARDS_PER_ACCOUNT
comment_forward_switch_delay = COMMENT_FORWARD_SWITCH_DELAY
chaohua_post_times = CHAOHUA_POST_TIMES
chaohua_sync_to_weibo = CHAOHUA_SYNC_TO_WEIBO
account_switch_delay = CHAOHUA_SWITCH_DELAY

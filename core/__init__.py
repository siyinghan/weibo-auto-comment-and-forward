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
pre_post_text = "#龚俊# 俊味仙 #龚俊孟剑卿# ｜#龚俊白衣公卿#"
post_link = "https://video.weibo.com/show?fid=1034:5249538768699394"
# 超话：暗河传、白衣公卿、凤舞九天、豹隐南山、龚俊温客行、龚俊
chaohua_urls = ["https://weibo.com/p/100808241b9ceecb561bd8de83d5e2f69b3beb",
                "https://weibo.com/p/10080837b798d2cfac00077133b309f2aac540",
                "https://weibo.com/p/10080894303e1cc6c5cef797640704c240fcfb",
                "https://weibo.com/p/1008083ce145cd2ed223247b5803187777c2b6",
                "https://weibo.com/p/100808d3fa73b65abd6f2e91cf143c1726319f",
                "https://weibo.com/p/100808b503e94e4f2f272c6e1cf79b59c41085"]

# 超话名称：用于日志显示。新增超话链接时，在这里补一个名字即可；
# 没有配置名字时会尝试从页面标题读取，最后才回退成链接。
chaohua_names = {
    "https://weibo.com/p/100808241b9ceecb561bd8de83d5e2f69b3beb": "暗河传",
    "https://weibo.com/p/10080837b798d2cfac00077133b309f2aac540": "白衣公卿",
    "https://weibo.com/p/10080894303e1cc6c5cef797640704c240fcfb": "凤舞九天",
    "https://weibo.com/p/1008083ce145cd2ed223247b5803187777c2b6": "豹隐南山",
    "https://weibo.com/p/100808d3fa73b65abd6f2e91cf143c1726319f": "龚俊温客行",
    "https://weibo.com/p/100808b503e94e4f2f272c6e1cf79b59c41085": "龚俊",
}

# 需要签到的超话列表：默认和 chaohua_urls 相同。
# 只签到、不发帖的超话，直接追加到这里，例如：
# signin_chaohua_urls = list(chaohua_urls) + ["https://weibo.com/p/100808..."]
# 发帖仍然只发在 chaohua_urls 的最后一个超话。
signin_chaohua_urls = list(chaohua_urls)

# 每个账号切换之间的等待秒数，避免微博提示“访问频繁”；建议不要小于 180。
account_switch_delay = 180

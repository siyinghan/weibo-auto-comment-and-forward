import logging
import os
import random
from string import ascii_lowercase

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

from config import ACCOUNTS
from core import comments_per_account, forwards_per_account, pre_post_text, post_link
from core.targets import DATA_FILES, load_weibo_details


def _require_details_index(details, weibo_details_index, filename):
    """
    Make sure the resolved target index exists in the selected JSON file.
    """
    if not 0 <= weibo_details_index < len(details):
        raise IndexError(
            f"Target index={weibo_details_index} is out of range for {filename} "
            f"({len(details)} entr{'y' if len(details) == 1 else 'ies'}; valid "
            f"index 0-{len(details) - 1}). The data file may have changed while "
            f"the task was running.")


def get_start_info(account_names, weibo_details_index, weibo_type):
    """
    Log the running accounts information.
    :param account_names: List[str]
    :param weibo_details_index: int
    :param weibo_type: str
    """
    account_dict = dict()
    for account_name in account_names:
        if account_name not in ACCOUNTS:
            raise KeyError(
                f"Account '{account_name}' is not defined in ACCOUNTS (config.py)")

    if weibo_type == "comment":
        count_per_account = comments_per_account
    elif weibo_type == "forward":
        count_per_account = forwards_per_account
    else:
        raise ValueError(f"Unknown weibo_type: {weibo_type}")

    for account_name in account_names:
        account_dict[account_name] = count_per_account

    details = load_weibo_details(weibo_type)
    _require_details_index(details, weibo_details_index, DATA_FILES[weibo_type])
    target = details[weibo_details_index]
    logging.info(
        f"Start {account_dict} | "
        f"{{'{target['tag']}': {target['total_comment_count']}}} ...")


def get_details(weibo_details_index, weibo_type):
    """
    Got the link and the total comments number of the target Weibo.
    :param weibo_details_index: int
    :param weibo_type: str
    :return: [str, int]
    """
    details = load_weibo_details(weibo_type)
    _require_details_index(details, weibo_details_index, DATA_FILES[weibo_type])
    target = details[weibo_details_index]
    return [target["link"], target["total_comment_count"]]


def generate_random_comment(count_num):
    """
    Generate comments with random letters and random emojis.
    :param count_num: int
    :return: str
    """
    with open("resources/random_text.txt") as file:
        random_item = random.choice(file.read().splitlines())
    with open("resources/weibo_emoji.txt") as file:
        emoji = file.read().splitlines()
        random_emoji1 = random.choice(emoji)
        random_emoji2 = random.choice(emoji)
    random_num = random.randint(1, 14)
    # generate random four letters 2 times, 1 put at the beginning, 2 put after {random_num} words
    random_letters = []
    for i in range(2):
        random_letters.append("".join(random.choice(ascii_lowercase) for _ in range(4)))
    comment = f"{random_letters[0]}{count_num}{random_emoji1}{random_item[:random_num]}" \
              f"{random_letters[1]}{random_item[random_num:]} {random_emoji2}"
    return comment


def generate_random_post():
    """
    Generate post with random letters and random emojis.
    :return: str
    """
    with open("resources/random_text_bygq.txt") as file:
        random_item = random.choice(file.read().splitlines())
    with open("resources/weibo_emoji.txt") as file:
        emoji = file.read().splitlines()
        random_emoji1 = random.choice(emoji)
        random_emoji2 = random.choice(emoji)
    random_letters = ["".join(random.choice(ascii_lowercase) for _ in range(4))]
    post_value = f"{pre_post_text} {random_letters[0]}{random_emoji1}{random_item}{random_emoji2}{post_link}"
    return post_value


def get_chrome_profile(account_name):
    """
    Return the Chrome profile name configured for an account in config.py.

    The value may be a profile name string or the legacy
    ``["profile name", count]`` list format.
    """
    try:
        account = ACCOUNTS[account_name]
    except KeyError:
        raise KeyError(
            f"Account '{account_name}' is not defined in ACCOUNTS (config.py)")
    return account[0] if isinstance(account, list) else account


def activate_chrome_driver(account_name, performance_logging=False):
    """
    Activate Selenium Chrome driver.
    :param account_name: str
    :param performance_logging: bool, capture network events (used by the
        Chaohua poster to read the publish API response)
    :return: driver
    """
    # get profile name
    profile = get_chrome_profile(account_name)
    # set driver
    options = webdriver.ChromeOptions()
    options.add_argument(r"--user-data-dir=~/Library/Application Support/Google/Chrome")
    options.add_argument(rf"--profile-directory={profile}")
    options.add_argument("--disable-extensions")
    if performance_logging:
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = webdriver.Chrome(options=options, service=Service(ChromeDriverManager().install()))
    driver.set_window_size(1400, 1000)
    return driver


def activate_firefox_driver():
    """Activate Selenium Firefox driver."""
    firefox_location = os.path.expanduser(r"~/Library/Application Support/Firefox/Profiles")
    firefox_profile = [_ for _ in os.listdir(firefox_location) if _.endswith("release")][0]
    driver = webdriver.Firefox(
        service=FirefoxService(GeckoDriverManager().install()),
        firefox_profile=webdriver.FirefoxProfile(os.path.join(firefox_location, firefox_profile)))
    driver.set_window_size(1400, 1000)
    return driver

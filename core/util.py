import json
import logging
import os
import random
from string import ascii_lowercase

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

from core import pre_post_text, post_link


def get_start_info(account_names, link_index, weibo_type):
    """
    Log the running accounts information.
    :param account_names: List[str]
    :param link_index: int
    :param weibo_type: str
    """
    account_dict = dict()
    if weibo_type == "comment":
        with open("conf/accounts.json", "r") as json_file:
            data = json.load(json_file)
            for account_name in account_names:
                comment_num = data[account_name][1]
                account_dict[account_name] = comment_num
        with open("conf/comment_data.json", "r") as json_file:
            data = json.load(json_file)
            weibo_tag = data["weibo_details"][link_index]["tag"]
            total_comment_count = data["weibo_details"][link_index]["total_comment_count"]
    elif weibo_type == "forward":
        with open("conf/accounts.json", "r") as json_file:
            data = json.load(json_file)
            for account_name in account_names:
                comment_num = data[account_name][1]
                account_dict[account_name] = comment_num
        with open("conf/forward_data.json", "r") as json_file:
            data = json.load(json_file)
            weibo_tag = data["weibo_details"][link_index]["tag"]
            total_comment_count = data["weibo_details"][link_index]["total_comment_count"]
    logging.info(f"Start {account_dict} | {{'{weibo_tag}': {total_comment_count}}} ...")


def get_details(weibo_details_index, weibo_type):
    """
    Got the link and the total comments number of the target Weibo.
    :param weibo_details_index: int
    :param weibo_type: str
    :return: [str, int]
    """
    if weibo_type == "comment":
        with open("conf/comment_data.json", "r") as json_file:
            data = json.load(json_file)
            weibo_link = data["weibo_details"][weibo_details_index]["link"]
            total_comment_count = data["weibo_details"][weibo_details_index]["total_comment_count"]
    elif weibo_type == "forward":
        with open("conf/forward_data.json", "r") as json_file:
            data = json.load(json_file)
            weibo_link = data["weibo_details"][weibo_details_index]["link"]
            total_comment_count = data["weibo_details"][weibo_details_index]["total_comment_count"]
    return [weibo_link, total_comment_count]


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
    with open("resources/random_text_ahz.txt") as file:
        random_item = random.choice(file.read().splitlines())
    with open("resources/weibo_emoji.txt") as file:
        emoji = file.read().splitlines()
        random_emoji1 = random.choice(emoji)
        random_emoji2 = random.choice(emoji)
    random_letters = ["".join(random.choice(ascii_lowercase) for _ in range(4))]
    post_value = f"{pre_post_text} {random_letters[0]}{random_emoji1}{random_item}{random_emoji2}{post_link}"
    return post_value


def activate_chrome_driver(account_name):
    """
    Activate Selenium Chrome driver.
    :param account_name: str
    :return: driver
    """
    # get profile name
    with open("conf/accounts.json", "r") as json_file:
        profile = json.load(json_file)[account_name][0]
    # set driver
    options = webdriver.ChromeOptions()
    options.add_argument(r"--user-data-dir=~/Library/Application Support/Google/Chrome")
    options.add_argument(rf"--profile-directory={profile}")
    options.add_argument("--disable-extensions")
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

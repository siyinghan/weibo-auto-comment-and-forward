"""
Generate Weibo comments and submit.
Click LIKE for each submitted comment.
"""
import json
import logging
import os.path
import random
import sys
from string import ascii_lowercase
from time import sleep

from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service as FirefoxService
from termcolor import colored
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

# create "log" folder if it is not exist
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


def get_start_info(account_names, link_index):
    """
    Log the running accounts information.
    :param account_names: List[str]
    :param link_index: int
    """
    account_dict = dict()
    with open("conf/accounts.json", "r") as json_file:
        data = json.load(json_file)
        for account_name in account_names:
            comment_num = data[account_name][1]
            account_dict[account_name] = comment_num
    with open("conf/data.json", "r") as json_file:
        data = json.load(json_file)
        weibo_tag = data["weibo_details"][link_index]["tag"]
        total_comment_count = data["weibo_details"][link_index]["total_comment_count"]
    logging.info(f"Start {account_dict} | {{'{weibo_tag}': {total_comment_count}}} ...")


def get_comment_details(weibo_details_index):
    """
    Got the link and the total comments number of the target Weibo.
    :param weibo_details_index: int
    :return: [str, int]
    """
    with open("conf/data.json", "r") as json_file:
        data = json.load(json_file)
        weibo_link = data["weibo_details"][weibo_details_index]["link"]
        total_comment_count = data["weibo_details"][weibo_details_index]["total_comment_count"]
    return [weibo_link, total_comment_count]


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


class Login:
    """
    Weibo login.
    """

    def run_chrome(self, account_name):
        """
        Chrome login.
        """
        with activate_chrome_driver(account_name) as driver:
            self.login(driver)

    def run_firefox(self):
        """
        Firefox login.
        """
        with activate_firefox_driver() as driver:
            self.login(driver)

    @staticmethod
    def login(driver):
        """
        Save login information in Chrome profiles for Weibo Accounts.
        """
        driver.implicitly_wait(10)
        driver.get(weibo_login_url)
        driver.find_element(
            by=By.XPATH, value="//*[@id='pl_login_form']/div/div[1]/a").click()
        sleep(0.5)
        driver.find_element(
            by=By.XPATH, value="//*[@id='pl_login_form']/div/div[1]/a").click()
        # wait for scanning and login
        sleep(20)


class CommentSender:
    """
    Send Weibo comments.
    """

    def __init__(self, account_names, weibo_details_index):
        self.account_names = account_names
        self.weibo_details_index = weibo_details_index
        self.like = True
        self.driver = None
        self.account_name = None
        self.new_comment_count = 0
        self.account_comment_num = 0
        self.weibo_url = get_comment_details(self.weibo_details_index)[0]
        self.total_comment_count = get_comment_details(self.weibo_details_index)[1]

    def run(self):
        """
        Run comment sender.
        """

        for account_name in self.account_names:
            self.account_name = account_name
            self.new_comment_count = 0

            with open("conf/accounts.json", "r") as json_file:
                self.account_comment_num = json.load(json_file)[account_name][1]

            with activate_chrome_driver(self.account_name) as driver:
                self.driver = driver
                logger_comment_sender.info(f"Chrome driver is activated with account '{self.account_name}'")
                self.send_and_like_comment()

            # set LIKE to True for the next account
            self.like = True

    def send_and_like_comment(self):
        """
        Go to the target Weibo.
        Input the comment and submit it.
        LIKE the comment.
        """
        # need to go to the login page first to log in
        self.driver.get(weibo_login_url)
        sleep(1)
        self.driver.get(self.weibo_url)
        logger_comment_sender.info(f"Open (send comments - '{self.account_name}'): {self.weibo_url}")
        sleep(4)

        # send comments and click like
        for i in range(self.account_comment_num):
            try:
                comment = self.driver.find_element(
                    by=By.XPATH, value="//*[@id='composerEle']/div[2]/div/div[1]/div/textarea")
                # clear the remaining texts before starting a new loop
                if i == 0 and comment.get_attribute("value"):
                    comment.clear()
                # generate comment value
                comment_value = self.generate_random_comment(self.total_comment_count + 1)
            except NoSuchElementException as _:
                # cookies expired
                logger_comment_sender.error(f"Please log in for account {self.account_name}")
                return None
            submit = self.driver.find_element(
                by=By.XPATH, value="//*[@id='composerEle']/div[2]/div/div[3]/div/button")

            comment.send_keys(comment_value)
            comment.send_keys(Keys.SPACE)
            submit.click()
            sleep(2)

            # check if comment submitted successfully
            _ = self.driver.find_element(by=By.XPATH, value="//*[@id='composerEle']/div[2]/div/div[1]/div/textarea")
            submit_flag = False if _.get_attribute("value") else True
            # submission succeeded
            if submit_flag:
                self.total_comment_count += 1
                self.new_comment_count += 1
                self.update_comment_count()
                logger_comment_sender.info(f"'{self.account_name}' #{self.new_comment_count}: '{comment_value}'")
                sleep(1)
                if self.like:
                    self.like_comment(self.driver)
                    sleep(1)
            # submission failed
            else:
                logger_comment_sender.error("Comment failed, please try again later")
                break

    def like_comment(self, driver):
        """
        LIKE the comment. Stop LIKE when it's not clickable.
        """
        like_button = driver.find_element(
            by=By.XPATH,
            value="//*[@id='scroller']/div[1]/div[1]/div/div/div/div[1]/div[2]/div[2]/div[2]/div[4]/button")
        like_button.click()
        sleep(1)
        try:
            like_button.find_element(by=By.CLASS_NAME, value="woo-like-an")
            logger_comment_sender.info(f"LIKE #{self.total_comment_count}")
        except NoSuchElementException as _:
            # LIKE failed
            self.like = False
            logger_comment_sender.warning(f"Failed to LIKE comment #{self.total_comment_count}")

    def update_comment_count(self):
        """
        Update the total comments number of the target Weibo.
        """
        with open("conf/data.json", "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        data["weibo_details"][self.weibo_details_index]["total_comment_count"] = self.total_comment_count
        with open("conf/data.json", "w", encoding="utf-8") as json_file:
            # ensure Chinese characters and JSON format
            json.dump(data, json_file, ensure_ascii=False, indent=2)

    @staticmethod
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

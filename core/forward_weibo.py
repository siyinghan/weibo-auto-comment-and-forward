import json
import logging
from time import sleep

from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from core import weibo_login_url
from core.util import get_details, activate_chrome_driver, generate_random_comment


class WeiboForwarder:
    """
    Forward Weibo.
    """

    def __init__(self, account_names, weibo_details_index):
        self.account_names = account_names
        self.weibo_details_index = weibo_details_index
        self.driver = None
        self.account_name = None
        self.new_comment_count = 0
        self.account_comment_num = 0
        self.weibo_url = get_details(self.weibo_details_index, "forward")[0]
        self.total_comment_count = get_details(self.weibo_details_index, "forward")[1]

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
                logging.info(f"Chrome driver is activated with account '{self.account_name}'")
                self.forward_comment()

    def forward_comment(self):
        """
        Go to the target Weibo.
        Forward the Weibo.
        """
        # need to go to the login page first to log in
        self.driver.get(weibo_login_url)
        sleep(1)
        self.driver.get(self.weibo_url)
        logging.info(f"Open (send comments - '{self.account_name}'): {self.weibo_url}")
        sleep(4)

        # forward the target Weibo
        for i in range(self.account_comment_num):
            try:
                # click "forward" button
                self.driver.find_element(
                    by=By.XPATH,
                    value="//*[@id='app']/div[1]/div[2]/div[2]/main/div/div"
                          "/div[2]/article/footer/div/div[1]/div/div/span/div") \
                    .click()
                comment = self.driver.find_element(
                    by=By.XPATH, value="//*[@id='composerEle']/div[2]/div/div[1]/div/textarea")
                # generate comment value
                comment_value = generate_random_comment(self.total_comment_count + 1)
            except NoSuchElementException as _:
                # cookies expired
                logging.error(f"Please log in for account {self.account_name}")
                return None
            submit = self.driver.find_element(
                by=By.XPATH, value="//*[@id='composerEle']/div[2]/div/div[3]/div/button")

            comment.clear()
            comment.send_keys(comment_value)
            comment.send_keys(Keys.SPACE)
            sleep(1)
            submit.click()
            self.total_comment_count += 1
            self.new_comment_count += 1
            self.update_comment_count()
            logging.info(f"'{self.account_name}' #{self.new_comment_count}: '{comment_value}'")
            sleep(2)

    def update_comment_count(self):
        """
        Update the total comments number of the target Weibo.
        """
        with open("conf/forward_data.json", "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        data["weibo_details"][self.weibo_details_index]["total_comment_count"] = self.total_comment_count
        with open("conf/forward_data.json", "w", encoding="utf-8") as json_file:
            # ensure Chinese characters and JSON format
            json.dump(data, json_file, ensure_ascii=False, indent=2)

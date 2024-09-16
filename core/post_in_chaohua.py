import logging
from time import sleep

from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By

from core import weibo_login_url, chaohua_url
from core.util import activate_chrome_driver, generate_random_comment, generate_random_post


class WeiboPoster:
    """
    Post Weibo in Chaohua.
    """

    def __init__(self, account_names):
        self.account_names = account_names
        self.driver = None
        self.account_name = None

    def run(self):
        """
        Run comment sender.
        """

        for account_name in self.account_names:
            self.account_name = account_name

            with activate_chrome_driver(self.account_name) as driver:
                self.driver = driver
                logging.info(f"Chrome driver is activated with account '{self.account_name}'")
                self.post()

    def post(self):
        """
        Post Weibo in Chaohua.
        """
        # need to go to the login page first to log in
        self.driver.get(weibo_login_url)
        sleep(1)
        self.driver.get(chaohua_url)
        logging.info(f"Open '{self.account_name}' to post Weibo")
        sleep(4)

        # post Weibo
        for i in range(7):
            try:
                textarea = self.driver.find_element(
                    by=By.XPATH,
                    value="//*[@id='Pl_Core_PublishV6__259']/div/div/div/div/div[2]/div[2]/div[1]/textarea")
            except NoSuchElementException as _:
                # cookies expired
                logging.error(f"Please log in for account {self.account_name}")
                return None

            submit = self.driver.find_element(
                by=By.XPATH, value="//*[@id='Pl_Core_PublishV6__259']/div/div/div/div/div[2]/div[2]/div[2]/div[1]/a")
            checkbox = self.driver.find_element(
                by=By.CSS_SELECTOR, value="input[node-type='transferkey']")
            post_value = generate_random_post()

            textarea.clear()
            textarea.send_keys(post_value)
            textarea.click()
            sleep(2)
            if checkbox.is_selected(): checkbox.click()
            sleep(1)
            submit.click()
            logging.info(f"Post from '{self.account_name}': '{post_value}'")
            sleep(4)

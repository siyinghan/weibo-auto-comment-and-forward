from time import sleep

from selenium.webdriver.common.by import By

from core import weibo_login_url
from core.util import activate_chrome_driver, activate_firefox_driver


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

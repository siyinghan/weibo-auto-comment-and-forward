import json
import logging
import os
import re
from time import sleep, strftime

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from core import comment_forward_switch_delay, forwards_per_account
from core.util import get_details, activate_chrome_driver, generate_random_comment


class NotLoggedInError(RuntimeError):
    """Raised when the Weibo page is opened without a valid login."""


class WeiboForwarder:
    """
    Forward Weibo.

    The 2026 Weibo redesign replaced the old ``#composerEle`` markup with the
    WooUI / wbpro inline composer.  Clicking the "转发" icon of the main post
    opens a composer with the textarea placeholder ``说说分享心得`` and a
    ``转发`` submit button.  The old absolute XPaths no longer match, so this
    implementation locates the stable parts of the new page instead.
    """

    FORWARD_TEXTAREA_SELECTORS = (
        "textarea[placeholder='说说分享心得']",
        "textarea[placeholder*='分享']",
    )
    FORWARD_BUTTON_TEXTS = ("转发", "发送", "发布")
    SUCCESS_TEXTS = ("转发成功", "发送成功", "发表成功")
    ERROR_TEXTS = ("转发失败", "发送失败", "发表失败", "失败", "稍后再试",
                   "访问频繁", "频繁", "验证码", "请先登录", "登录后", "异常", "出错",
                   "上限", "次数", "限制", "明天", "用完", "已达")
    LOGIN_TEXTS = ("扫码登录", "请先登录", "登录后", "登录/注册")
    RATE_LIMIT_TEXTS = ("频繁", "稍后再试", "验证码", "上限", "次数", "限制",
                        "明天", "用完", "已达", "异常", "出错")

    def __init__(self, account_names, weibo_details_index):
        self.account_names = account_names
        self.weibo_details_index = weibo_details_index
        self.driver = None
        self.account_name = None
        self.new_forward_count = 0
        self.account_forward_num = forwards_per_account
        self.weibo_url = get_details(self.weibo_details_index, "forward")[0]
        self.total_comment_count = get_details(self.weibo_details_index, "forward")[1]
        self._results = {}
        self._status = "ok"
        self._error = None

    def run(self):
        """
        Run the forwarder for every account.
        """
        self._results = {}

        for index, account_name in enumerate(self.account_names):
            self.account_name = account_name
            self.new_forward_count = 0
            self._status = "ok"
            self._error = None
            result = {"sent": 0, "target": 0, "status": "ok", "error": None}
            self._results[account_name] = result

            try:
                self.account_forward_num = forwards_per_account
                result["target"] = self.account_forward_num

                with activate_chrome_driver(self.account_name) as driver:
                    self.driver = driver
                    logging.info(f"Chrome driver is activated with account '{self.account_name}'")
                    if not self._open_target_page():
                        result["status"] = "not_logged_in"
                    else:
                        self.forward_weibo()
                        result["sent"] = self.new_forward_count
                        result["status"] = self._status
                        result["error"] = self._error
            except NotLoggedInError:
                logging.error(f"Please log in for account {account_name}")
                result["sent"] = self.new_forward_count
                result["status"] = "not_logged_in"
            except Exception as exc:  # one broken account must not stop the others
                logging.error(f"Account '{account_name}' stopped: {exc}", exc_info=True)
                result["sent"] = self.new_forward_count
                result["status"] = "error"
                result["error"] = str(exc)
                self._dump_diagnostics("account-error")
            finally:
                self.driver = None
                # Give Chrome a moment to release the shared user-data-dir.
                sleep(2)

            # Configured in config.py (COMMENT_FORWARD_SWITCH_DELAY).
            if comment_forward_switch_delay and index < len(self.account_names) - 1:
                next_account = self.account_names[index + 1]
                logging.info(
                    f"Waiting {comment_forward_switch_delay}s before the next account "
                    f"('{next_account}') to avoid Weibo rate limiting ...")
                sleep(comment_forward_switch_delay)

        self._print_summary()

    def _print_summary(self):
        """
        Log the number of forwards sent by every account, like the Chaohua
        posting summary.
        """
        lines = ["", "==================== 运行汇总 ===================="]
        total_sent = 0
        total_target = 0

        for name in self.account_names:
            result = self._results.get(name)
            if result is None:
                lines.append(f"{name}: 未运行")
                continue

            sent = result.get("sent", 0)
            target = result.get("target", 0)
            total_sent += sent
            total_target += target

            status = result.get("status", "ok")
            if status == "not_logged_in":
                status_text = "未登录，已跳过"
            elif status == "rate_limited":
                status_text = "触发微博限制，已跳过"
            elif status == "error":
                status_text = "异常，已跳过"
            elif target == 0:
                status_text = "无任务"
            elif sent >= target:
                status_text = "正常"
            else:
                status_text = "未完成"

            lines.append(f"{name}: 转发 {sent}/{target}；{status_text}")

        lines.append(f"合计: 转发 {total_sent}/{total_target}")
        lines.append("==================================================")
        logging.info("\n".join(lines))

    def forward_weibo(self):
        """
        Go to the target Weibo and forward it for the current account.
        """
        for i in range(self.account_forward_num):
            count_num = self.total_comment_count + 1
            forward_value = generate_random_comment(count_num)
            try:
                textarea = self._open_forward_composer()
                self._fill_forward_composer(textarea, forward_value)

                submit = self._find_submit_button(textarea)
                if submit is None:
                    raise RuntimeError("could not find the 转发 button")

                # The button starts disabled and is enabled after typing.
                WebDriverWait(self.driver, 10).until(lambda _: submit.is_enabled())
                logging.info(
                    f"Forwarding {i + 1}/{self.account_forward_num} "
                    f"as '{self.account_name}' ...")
                self._click(submit)
            except NotLoggedInError as exc:
                logging.error(f"Please log in for account {self.account_name}")
                self._status = "not_logged_in"
                self._error = str(exc)
                return
            except Exception as exc:
                logging.error(
                    f"Forward {i + 1} failed: {exc}; skip the remaining forwards "
                    f"for '{self.account_name}' and continue with the next account.",
                    exc_info=True)
                self._status = "error"
                self._error = str(exc)
                self._dump_diagnostics("forward-error")
                return

            status, detail = self._wait_forward_result()
            if status == "login":
                logging.error(f"Please log in for account {self.account_name}")
                self._status = "not_logged_in"
                self._error = detail
                return
            if status != "success":
                logging.error(f"Forward failed: {detail}")
                limited = any(keyword in detail for keyword in self.RATE_LIMIT_TEXTS)
                self._status = "rate_limited" if limited else "error"
                self._error = detail
                if limited:
                    logging.error(
                        f"Weibo is rate limiting account '{self.account_name}'; "
                        "skip the remaining forwards for this account and continue "
                        "with the next account.")
                else:
                    logging.error(
                        f"Skip the remaining forwards for '{self.account_name}' "
                        "and continue with the next account.")
                self._dump_diagnostics("forward-failed")
                return

            # Only a confirmed forward is counted.
            self.total_comment_count = count_num
            self.new_forward_count += 1
            self.update_comment_count()
            logging.info(f"'{self.account_name}' #{self.new_forward_count}: '{forward_value}'")

            # The inline composer normally closes after a successful forward.
            # If it stays open, the next loop reuses it.
            self._wait_forward_composer_closed(timeout=8)
            sleep(2)

    def update_comment_count(self):
        """
        Update the total forwards number of the target Weibo.
        """
        with open("conf/forward_data.json", "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        data["weibo_details"][self.weibo_details_index]["total_comment_count"] = self.total_comment_count
        with open("conf/forward_data.json", "w", encoding="utf-8") as json_file:
            # ensure Chinese characters and JSON format
            json.dump(data, json_file, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Page / composer helpers
    # ------------------------------------------------------------------
    def _open_target_page(self):
        """
        Open the target Weibo directly and make sure the profile is logged in.

        The login state is stored in the Chrome profile cookies, so opening the
        Weibo home page/login page first is unnecessary.
        """
        self.driver.get(self.weibo_url)
        logging.info(f"Open (forward - '{self.account_name}'): {self.weibo_url}")

        try:
            WebDriverWait(self.driver, 30).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete")
        except TimeoutException:
            pass

        if not self._is_logged_in():
            logging.error(f"Please log in for account {self.account_name}")
            return False
        return True

    def _is_logged_in(self):
        """
        Check the login state through the Weibo page config object.
        """
        try:
            WebDriverWait(self.driver, 15).until(
                lambda driver: driver.execute_script("return !!window.$CONFIG"))
            return bool(self.driver.execute_script(
                "return !!(window.$CONFIG && (window.$CONFIG.user || window.$CONFIG.uid))"))
        except (TimeoutException, WebDriverException):
            return False

    def _find_forward_button(self):
        """
        Find the "转发" icon of the main post (not the icons on comments and
        not the icon of the embedded quoted Weibo).

        The main post footer contains the "分享这条博文" entry.  The footer of
        an embedded repost card does not, so it is used to tell them apart.
        """
        return self.driver.execute_script(
            """
            const visible = (el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
            const icons = Array.from(document.querySelectorAll("[title='转发']")).filter(visible);
            // Do not use the forward icons of individual comments.
            let postIcons = icons.filter((el) => !el.closest('.wbpro-list'));
            // The main post is rendered before the comment composer.  Keep the
            // icons before it so a "related posts" feed further down the page
            // cannot be selected.
            const commentBox = document.querySelector("textarea[placeholder='发布你的评论']");
            if (commentBox) {
                postIcons = postIcons.filter(
                    (el) => el.compareDocumentPosition(commentBox) & Node.DOCUMENT_POSITION_FOLLOWING);
            }
            // The outer post footer contains "分享这条博文"; the footer of an
            // embedded quoted post does not.  Take the last match because the
            // outer footer is rendered after the quoted card.
            const preferred = postIcons.filter((el) => {
                const footer = el.closest('footer');
                return footer && (footer.innerText || '').includes('分享');
            }).pop();
            return preferred || postIcons[postIcons.length - 1] || null;
            """)

    def _wait_forward_button(self, timeout=20):
        """
        Wait for the main post's forward icon to be rendered.
        """
        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(
                lambda _: self._find_forward_button())
        except TimeoutException:
            return None

    def _find_forward_textarea(self):
        """
        Return the visible inline forward composer textarea, if present.
        """
        for selector in self.FORWARD_TEXTAREA_SELECTORS:
            textarea = self._first_visible(
                self.driver.find_elements(By.CSS_SELECTOR, selector))
            if textarea is not None:
                return textarea

        # Fallback for a placeholder change: the forward composer is only
        # rendered with the #repost hash.  Do not mistake the normal comment
        # textarea (发布你的评论) for it.
        if "#repost" in (self.driver.current_url or ""):
            for textarea in self.driver.find_elements(By.CSS_SELECTOR, "textarea"):
                if not self._is_displayed(textarea):
                    continue
                if (textarea.get_attribute("placeholder") or "") == "发布你的评论":
                    continue
                return textarea
        return None

    def _open_forward_composer(self, timeout=20):
        """
        Open the inline forward composer and return its textarea.
        """
        textarea = self._find_forward_textarea()
        if textarea is not None:
            return textarea

        button = self._wait_forward_button()
        if button is None:
            if not self._is_logged_in():
                raise NotLoggedInError(
                    f"Account '{self.account_name}' is not logged in. "
                    "Please log in with login_chrome.py before forwarding.")
            self._dump_diagnostics("forward-button-missing")
            raise RuntimeError(
                "could not find the 转发 button of the main post; the page layout may have changed")

        self._click(button)
        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(
                lambda _: self._find_forward_textarea())
        except TimeoutException:
            if not self._is_logged_in():
                raise NotLoggedInError(
                    f"Account '{self.account_name}' is not logged in. "
                    "Please log in with login_chrome.py before forwarding.")
            raise RuntimeError(
                "could not open the forward composer (说说分享心得); "
                "the page layout may have changed")

    def _fill_forward_composer(self, textarea, forward_value):
        """
        Clear the quoted prefill and type the generated forward message.
        """
        self._click(textarea)

        # The new composer pre-fills "//@<author>:<original text>".
        # The old code cleared it, so keep forwarding only our own text.
        textarea.send_keys(Keys.COMMAND, "a")
        textarea.send_keys(Keys.DELETE)
        if textarea.get_attribute("value"):
            textarea.clear()
        if textarea.get_attribute("value"):
            self.driver.execute_script(
                """
                const textarea = arguments[0];
                textarea.value = '';
                textarea.dispatchEvent(new Event('input', {bubbles: true}));
                textarea.dispatchEvent(new Event('change', {bubbles: true}));
                """,
                textarea,
            )
        if textarea.get_attribute("value"):
            raise RuntimeError("could not clear the quoted prefill in the forward composer")

        textarea.send_keys(forward_value)
        if not self._composer_contains(textarea, forward_value):
            # Some Vue versions need an explicit input event after send_keys.
            logging.warning("The typed forward was not registered, dispatching an input event")
            self.driver.execute_script(
                """
                const textarea = arguments[0];
                const value = arguments[1];
                textarea.value = value;
                textarea.dispatchEvent(new Event('input', {bubbles: true}));
                textarea.dispatchEvent(new Event('change', {bubbles: true}));
                """,
                textarea,
                forward_value,
            )
            if not self._composer_contains(textarea, forward_value):
                raise RuntimeError("could not write the forward text into the composer")

    def _find_submit_button(self, textarea):
        """
        Find the ``转发`` button that belongs to the inline composer.
        """
        condition = " or ".join(
            f"normalize-space(.)='{text}'" for text in self.FORWARD_BUTTON_TEXTS)

        try:
            scope = textarea.find_element(
                By.XPATH, "./ancestor::div[contains(@class, 'woo-box-flex')][1]")
            button = self._first_visible(
                scope.find_elements(By.XPATH, f".//button[{condition}]"))
            if button is not None:
                return button
        except (NoSuchElementException, StaleElementReferenceException, WebDriverException):
            pass

        return self._first_visible(
            self.driver.find_elements(By.XPATH, f"//button[{condition}]"))

    def _wait_forward_result(self, timeout=20):
        """
        Wait for the result of the forward submission.
        """
        def check(_):
            messages = self._visible_message_texts()
            for text in messages:
                if any(keyword in text for keyword in self.LOGIN_TEXTS):
                    return "login", text
            for text in messages:
                if any(keyword in text for keyword in self.SUCCESS_TEXTS):
                    return "success", text
            for text in messages:
                if any(keyword in text for keyword in self.ERROR_TEXTS):
                    return "error", text

            # The inline composer closes after a successful forward.
            if self._find_forward_textarea() is None:
                return "success", "the forward composer closed"
            return None

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(check)
        except TimeoutException:
            return "error", "no success signal (the forward composer is still open)"

    def _wait_forward_composer_closed(self, timeout=8):
        try:
            WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(
                lambda _: self._find_forward_textarea() is None)
        except TimeoutException:
            pass

    @staticmethod
    def _composer_contains(textarea, value):
        current = textarea.get_attribute("value") or ""
        return value[:10] in current or value.strip()[-10:] in current

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------
    def _visible_message_texts(self):
        """
        Collect the text of visible toasts/dialogs (forward result messages).
        """
        texts = []
        for element in self.driver.find_elements(
                By.CSS_SELECTOR,
                ".woo-toast-main, .woo-toast, [class*='toast'], .woo-dialog-main, "
                ".woo-modal-main, [role='dialog']"):
            try:
                if not element.is_displayed():
                    continue
                text = (element.text or "").strip()
            except StaleElementReferenceException:
                continue
            if text:
                texts.append(text)
        return texts

    @staticmethod
    def _is_displayed(element):
        try:
            return element.is_displayed()
        except StaleElementReferenceException:
            return False

    @classmethod
    def _first_visible(cls, elements):
        for element in elements:
            if cls._is_displayed(element):
                return element
        return None

    def _click(self, element):
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'center'});", element)
        except WebDriverException:
            pass
        try:
            element.click()
        except (ElementClickInterceptedException, ElementNotInteractableException,
                StaleElementReferenceException, WebDriverException):
            self.driver.execute_script("arguments[0].click();", element)

    def _dump_diagnostics(self, tag):
        if self.driver is None:
            return
        try:
            os.makedirs("log", exist_ok=True)
            safe_account = re.sub(
                r"[^0-9A-Za-z\u4e00-\u9fff_.-]+", "_", self.account_name or "unknown")
            base = f"log/forward-{safe_account}-{tag}-{strftime('%Y%m%d-%H%M%S')}"
            self.driver.save_screenshot(f"{base}.png")
            with open(f"{base}.html", "w", encoding="utf-8") as file:
                file.write(self.driver.page_source)
            logging.info(f"Saved diagnostics to {base}.png and {base}.html")
        except Exception as exc:  # diagnostics must never hide the real error
            logging.warning(f"Could not save diagnostics: {exc}")

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

from core import comment_forward_switch_delay, comments_per_account
from core.util import get_details, activate_chrome_driver, generate_random_comment


class NotLoggedInError(RuntimeError):
    """Raised when the Weibo page is opened without a valid login."""


class CommentSender:
    """
    Send Weibo comments and LIKE them.

    The 2026 Weibo redesign replaced the old ``#composerEle`` markup with the
    WooUI / wbpro SPA.  The old absolute XPaths therefore no longer match and
    every account was reported as "not logged in".  This implementation uses
    the stable parts of the new page instead:

    * the composer textarea (``发布你的评论``),
    * the WooUI primary button whose text is ``评论``,
    * the comment list (``.wbpro-list``) and its ``button.woo-like-main``.
    """

    # Selectors are ordered from the most specific to the most generic.
    COMMENT_TEXTAREA_SELECTORS = (
        "textarea[placeholder='发布你的评论']",
        "textarea[placeholder*='评论']",
        ".wbpro-form textarea",
    )
    COMMENT_BUTTON_TEXTS = ("评论", "发送")
    NEWEST_SORT_TEXT = "按倒序"
    SUCCESS_TEXTS = ("评论成功", "发送成功", "发表成功")
    ERROR_TEXTS = ("评论失败", "发送失败", "发表失败", "失败", "稍后再试",
                   "访问频繁", "频繁", "验证码", "请先登录", "登录后", "异常", "出错",
                   "上限", "次数", "限制", "明天", "用完", "已达")
    LOGIN_TEXTS = ("扫码登录", "请先登录", "登录后", "登录/注册")
    RATE_LIMIT_TEXTS = ("频繁", "稍后再试", "验证码", "上限", "次数", "限制",
                        "明天", "用完", "已达", "异常", "出错")

    def __init__(self, account_names, weibo_details_index):
        self.account_names = account_names
        self.weibo_details_index = weibo_details_index
        self.like = True
        self.driver = None
        self.account_name = None
        self.new_comment_count = 0
        self.account_comment_num = comments_per_account
        self.weibo_url = get_details(self.weibo_details_index, "comment")[0]
        self.total_comment_count = get_details(self.weibo_details_index, "comment")[1]
        self._results = {}
        self._status = "ok"
        self._error = None

    def run(self):
        """
        Run comment sender.
        """
        self._results = {}

        for index, account_name in enumerate(self.account_names):
            self.account_name = account_name
            self.new_comment_count = 0
            # A failed LIKE must only disable LIKE for the current account.
            self.like = True
            self._status = "ok"
            self._error = None
            result = {"sent": 0, "target": 0, "status": "ok", "error": None}
            self._results[account_name] = result

            try:
                self.account_comment_num = comments_per_account
                result["target"] = self.account_comment_num

                with activate_chrome_driver(self.account_name) as driver:
                    self.driver = driver
                    logging.info(f"Chrome driver is activated with account '{self.account_name}'")
                    if not self._open_target_page():
                        result["status"] = "not_logged_in"
                    else:
                        self.send_and_like_comment()
                        result["sent"] = self.new_comment_count
                        result["status"] = self._status
                        result["error"] = self._error
            except NotLoggedInError:
                logging.error(f"Please log in for account {account_name}")
                result["sent"] = self.new_comment_count
                result["status"] = "not_logged_in"
            except Exception as exc:  # one broken account must not stop the others
                logging.error(f"Account '{account_name}' stopped: {exc}", exc_info=True)
                result["sent"] = self.new_comment_count
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
        Log the number of comments sent by every account, like the Chaohua
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

            lines.append(f"{name}: 评论 {sent}/{target}；{status_text}")

        lines.append(f"合计: 评论 {total_sent}/{total_target}")
        lines.append("==================================================")
        logging.info("\n".join(lines))

    def send_and_like_comment(self):
        """
        Go to the target Weibo, send comments and LIKE each of them.
        """
        # Showing the newest comments first makes it possible to find the
        # comment we just posted (the default order is 按热度).
        self._ensure_newest_sort()

        for i in range(self.account_comment_num):
            count_num = self.total_comment_count + 1
            comment_value = generate_random_comment(count_num)
            try:
                textarea = self._wait_for_composer()
                self._fill_composer(textarea, comment_value)

                submit = self._find_submit_button(textarea)
                if submit is None:
                    raise RuntimeError("could not find the 评论 button")

                # The button starts disabled and is enabled after typing.
                WebDriverWait(self.driver, 10).until(lambda _: submit.is_enabled())
                logging.info(
                    f"Posting comment {i + 1}/{self.account_comment_num} "
                    f"as '{self.account_name}' ...")
                self._click(submit)
            except NotLoggedInError as exc:
                logging.error(f"Please log in for account {self.account_name}")
                self._status = "not_logged_in"
                self._error = str(exc)
                return
            except Exception as exc:
                logging.error(
                    f"Comment {i + 1} failed: {exc}; skip the remaining comments "
                    f"for '{self.account_name}' and continue with the next account.",
                    exc_info=True)
                self._status = "error"
                self._error = str(exc)
                self._dump_diagnostics("comment-error")
                return

            status, detail = self._wait_comment_result(comment_value, count_num)
            if status == "login":
                logging.error(f"Please log in for account {self.account_name}")
                self._status = "not_logged_in"
                self._error = detail
                return
            if status != "success":
                logging.error(f"Comment failed: {detail}")
                limited = any(keyword in detail for keyword in self.RATE_LIMIT_TEXTS)
                self._status = "rate_limited" if limited else "error"
                self._error = detail
                if limited:
                    logging.error(
                        f"Weibo is rate limiting account '{self.account_name}'; "
                        "skip the remaining comments for this account and continue "
                        "with the next account.")
                else:
                    logging.error(
                        f"Skip the remaining comments for '{self.account_name}' "
                        "and continue with the next account.")
                self._dump_diagnostics("comment-failed")
                return

            # Only a confirmed comment is counted.
            self.total_comment_count = count_num
            self.new_comment_count += 1
            self.update_comment_count()
            logging.info(f"'{self.account_name}' #{self.new_comment_count}: '{comment_value}'")
            sleep(1)

            if self.like:
                self.like_comment(comment_value, count_num)
                sleep(1)
            sleep(1)

    def update_comment_count(self):
        """
        Update the total comments number of the target Weibo.
        """
        with open("conf/comment_data.json", "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        data["weibo_details"][self.weibo_details_index]["total_comment_count"] = self.total_comment_count
        with open("conf/comment_data.json", "w", encoding="utf-8") as json_file:
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
        logging.info(f"Open (send comments - '{self.account_name}'): {self.weibo_url}")

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

    def _wait_for_composer(self, timeout=25):
        """
        Wait for the comment textarea of the new WooUI composer.
        """
        def find(_):
            for selector in self.COMMENT_TEXTAREA_SELECTORS:
                textarea = self._first_visible(
                    self.driver.find_elements(By.CSS_SELECTOR, selector))
                if textarea is not None:
                    return textarea
            return None

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(find)
        except TimeoutException:
            if not self._is_logged_in():
                raise NotLoggedInError(
                    f"Account '{self.account_name}' is not logged in. "
                    "Please log in with login_chrome.py before commenting.")
            raise RuntimeError(
                "could not find the comment box (发布你的评论); the page layout may have changed")

    def _fill_composer(self, textarea, comment_value):
        """
        Clear the composer and type the generated comment.
        """
        self._click(textarea)

        if textarea.get_attribute("value"):
            # clear() is not reliable on every textarea; select-all + delete.
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
                raise RuntimeError("could not clear the existing text in the comment box")

        textarea.send_keys(comment_value)
        if not self._composer_contains(textarea, comment_value):
            # Some Vue versions need an explicit input event after send_keys.
            logging.warning("The typed comment was not registered, dispatching an input event")
            self.driver.execute_script(
                """
                const textarea = arguments[0];
                const value = arguments[1];
                textarea.value = value;
                textarea.dispatchEvent(new Event('input', {bubbles: true}));
                textarea.dispatchEvent(new Event('change', {bubbles: true}));
                """,
                textarea,
                comment_value,
            )
            if not self._composer_contains(textarea, comment_value):
                raise RuntimeError("could not write the comment into the composer")

    def _find_submit_button(self, textarea):
        """
        Find the ``评论`` button that belongs to the composer.

        The button is not inside the textarea's ``.wbpro-form`` wrapper, so
        the closest WooUI flex ancestor is used as the search scope first.
        """
        condition = " or ".join(
            f"normalize-space(.)='{text}'" for text in self.COMMENT_BUTTON_TEXTS)

        try:
            scope = textarea.find_element(
                By.XPATH, "./ancestor::div[contains(@class, 'woo-box-flex')][1]")
            button = self._first_visible(
                scope.find_elements(By.XPATH, f".//button[{condition}]"))
            if button is not None:
                return button
        except (NoSuchElementException, StaleElementReferenceException, WebDriverException):
            pass

        # Fallback: the page only has one visible 评论 submit button.
        return self._first_visible(
            self.driver.find_elements(By.XPATH, f"//button[{condition}]"))

    def _wait_comment_result(self, comment_value, count_num, timeout=20):
        """
        Wait for the result of the comment submission.

        Returns ``("success", detail)``, ``("error", detail)`` or
        ``("login", detail)``.
        """
        token = self._comment_token(comment_value, count_num)

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

            value = self._composer_value()
            # A removed composer or a cleared textarea means the comment was
            # submitted (the new composer only resets after a successful POST).
            if value is None:
                return "success", "the composer closed"
            if not value.strip():
                return "success", "the composer was cleared"

            if self._has_comment(token):
                return "success", "the new comment appeared in the list"
            return None

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(check)
        except TimeoutException:
            return "error", "no success signal (the comment box still contains text)"

    def _composer_value(self):
        """
        Return the current textarea value, or ``None`` if the composer is gone.
        """
        textarea = None
        for selector in self.COMMENT_TEXTAREA_SELECTORS:
            textarea = self._first_visible(
                self.driver.find_elements(By.CSS_SELECTOR, selector))
            if textarea is not None:
                break
        if textarea is None:
            return None
        try:
            return textarea.get_attribute("value") or ""
        except StaleElementReferenceException:
            return None

    @staticmethod
    def _composer_contains(textarea, value):
        current = textarea.get_attribute("value") or ""
        return value[:10] in current or value.strip()[-10:] in current

    def _ensure_newest_sort(self):
        """
        Switch the comment list to 按倒序 (newest first) when it is not active.
        """
        if self._active_sort() == self.NEWEST_SORT_TEXT:
            return True

        try:
            # The comment list is rendered asynchronously after the post.
            WebDriverWait(self.driver, 15, poll_frequency=0.3).until(
                lambda driver: driver.find_elements(By.CSS_SELECTOR, ".wbpro-tab3 .item"))
            for tab in self.driver.find_elements(By.CSS_SELECTOR, ".wbpro-tab3 .item"):
                if (tab.text or "").strip() != self.NEWEST_SORT_TEXT:
                    continue
                self._click(tab)
                WebDriverWait(self.driver, 10, poll_frequency=0.3).until(
                    lambda _: self._active_sort() == self.NEWEST_SORT_TEXT)
                sleep(1)
                return True
        except (TimeoutException, WebDriverException):
            pass

        logging.warning("Could not switch the comment list to 按倒序")
        return False

    def _active_sort(self):
        try:
            active = self.driver.find_elements(By.CSS_SELECTOR, ".wbpro-tab3 .item.curr")
            return (active[0].text or "").strip() if active else None
        except (StaleElementReferenceException, WebDriverException):
            return None

    # ------------------------------------------------------------------
    # LIKE helpers
    # ------------------------------------------------------------------
    def like_comment(self, comment_value, count_num):
        """
        LIKE the comment that was just posted.  Stop LIKEing for this account
        when the comment cannot be found or the button does not react.
        """
        token = self._comment_token(comment_value, count_num)

        item = self._wait_comment_item(token, timeout=15)
        if item is None:
            logging.warning(
                f"Could not find the new comment to LIKE (#{count_num}); skip LIKE")
            self.like = False
            return False

        try:
            like_button = item.find_element(By.CSS_SELECTOR, "button.woo-like-main")
        except (NoSuchElementException, StaleElementReferenceException):
            logging.warning(f"LIKE button of comment #{count_num} was not found")
            self.like = False
            return False

        if self._comment_is_liked(token):
            logging.info(f"LIKE #{count_num} (already liked)")
            return True

        self._click(like_button)
        try:
            WebDriverWait(self.driver, 5, poll_frequency=0.3).until(
                lambda _: self._comment_is_liked(token))
            logging.info(f"LIKE #{count_num}")
            return True
        except TimeoutException:
            self.like = False
            logging.warning(f"Failed to LIKE comment #{count_num}")
            return False

    def _wait_comment_item(self, token, timeout=15):
        """
        Wait for the comment item whose text contains the unique token.
        """
        def find(_):
            for item in self.driver.find_elements(By.CSS_SELECTOR, ".wbpro-list > .item1"):
                try:
                    if token in (item.text or ""):
                        return item
                except StaleElementReferenceException:
                    continue
            return None

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(find)
        except TimeoutException:
            return None

    def _has_comment(self, token):
        """
        Check whether a posted comment is already rendered in the list.
        """
        try:
            return bool(self.driver.execute_script(
                """
                const token = arguments[0];
                const items = document.querySelectorAll('.wbpro-list .item1 .text');
                for (const item of items) {
                    if ((item.innerText || '').includes(token)) return true;
                }
                return false;
                """,
                token))
        except WebDriverException:
            return False

    def _comment_is_liked(self, token):
        """
        Check the ``woo-like-an`` class of the LIKE icon of the new comment.
        """
        try:
            return bool(self.driver.execute_script(
                """
                const token = arguments[0];
                const items = document.querySelectorAll('.wbpro-list > .item1');
                for (const item of items) {
                    if (!(item.innerText || '').includes(token)) continue;
                    const button = item.querySelector('button.woo-like-main');
                    return !!(button && button.querySelector('.woo-like-an'));
                }
                return false;
                """,
                token))
        except WebDriverException:
            return False

    @staticmethod
    def _comment_token(comment_value, count_num):
        # generate_random_comment() starts with four letters followed by the
        # running number, which makes this unique across the target Weibo.
        return f"{comment_value[:4]}{count_num}"

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------
    def _visible_message_texts(self):
        """
        Collect the text of visible toasts/dialogs (comment result messages).
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
            base = f"log/comment-{safe_account}-{tag}-{strftime('%Y%m%d-%H%M%S')}"
            self.driver.save_screenshot(f"{base}.png")
            with open(f"{base}.html", "w", encoding="utf-8") as file:
                file.write(self.driver.page_source)
            logging.info(f"Saved diagnostics to {base}.png and {base}.html")
        except Exception as exc:  # diagnostics must never hide the real error
            logging.warning(f"Could not save diagnostics: {exc}")

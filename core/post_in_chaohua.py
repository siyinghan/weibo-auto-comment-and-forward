import json
import logging
import os
import re
from base64 import b64decode
from time import sleep, strftime

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from core import account_switch_delay, chaohua_names, chaohua_urls, signin_chaohua_urls
from core.util import activate_chrome_driver, generate_random_post


class NotLoggedInError(RuntimeError):
    """Raised when a Chaohua page is opened without a valid Weibo login."""


class WeiboPoster:
    """
    Post Weibo in Chaohua.

    The 2026 Chaohua redesign replaced the old ``Pl_Core_PublishV6__*``
    markup with a new SPA.  Long absolute XPaths (the previous approach)
    break as soon as the header is re-rendered, so this implementation
    locates elements by their visible text and by the stable WooUI class
    names of the composer.

    Before publishing, every configured Chaohua is followed and checked
    in (签到), matching the behaviour of the old "register in Chaohua"
    loop on the redesigned page.
    """

    # How many posts to publish for every account.
    POST_TIMES = 6
    # The old code un-checked "同步到微博"; keep that behaviour so the
    # posts only go to the Chaohua and not to the personal timeline.
    SYNC_TO_WEIBO = False

    PUBLISH_BUTTON_TEXTS = ("发帖", "我来发一帖", "发帖互动")
    FOLLOW_BUTTON_TEXTS = ("加关注", "关注", "+关注")
    SEND_BUTTON_TEXTS = ("发送", "发布")
    FOLLOW_DIALOG_TEXT = "关注超话后才能发帖"
    SUCCESS_TEXTS = ("发布成功", "发送成功", "发表成功")
    ERROR_TEXTS = ("发布失败", "发帖失败", "发送失败", "失败", "稍后再试",
                   "请先登录", "登录后", "频繁", "验证码", "异常", "出错")
    SIGN_BUTTON_TEXTS = ("签到", "已签到")
    SIGN_SUCCESS_TEXTS = ("签到成功", "已签到", "今天已签到")
    SIGN_ERROR_TEXTS = ("签到失败", "请先登录", "请先关注", "登录后")

    def __init__(self, account_names, post_times=None):
        self.account_names = list(account_names)
        self.post_times = self.POST_TIMES if post_times is None else post_times
        self.driver = None
        self.account_name = None
        self._results = {}
        self._current_result = self._new_result()
        self._chaohua_name_cache = {}

    def run(self):
        """
        Publish posts for every configured account, then log a summary.
        """
        self._results = {}
        stopped = False

        for index, account_name in enumerate(self.account_names):
            self.account_name = account_name
            result = self._new_result()
            self._results[account_name] = result
            self._current_result = result

            try:
                with activate_chrome_driver(account_name, performance_logging=True) as driver:
                    self.driver = driver
                    try:
                        driver.execute_cdp_cmd("Network.enable", {})
                    except WebDriverException:
                        pass
                    logging.info(f"Chrome driver is activated with account '{self.account_name}'")
                    self.post()
            except NotLoggedInError as exc:
                logging.error(str(exc))
                logging.error("Stop: a Weibo login is required before posting.")
                result["status"] = "not_logged_in"
                stopped = True
            except Exception as exc:
                logging.error(f"Account '{account_name}' stopped: {exc}", exc_info=True)
                result["status"] = "error"
                result["error"] = str(exc)
                self._dump_diagnostics("account-error")
            finally:
                self.driver = None
                self._current_result = self._new_result()
                # Give Chrome a moment to release the shared user-data-dir
                # before the next profile is started.
                sleep(2)

            if stopped:
                break

            # Weibo throttles rapid account switching from the same IP.
            # Waiting here is what makes the second and later profiles work.
            if index < len(self.account_names) - 1:
                next_account = self.account_names[index + 1]
                logging.info(
                    f"Waiting {account_switch_delay}s before the next account "
                    f"('{next_account}') to avoid Weibo rate limiting ...")
                sleep(account_switch_delay)

        self._print_summary(stopped)

    def _new_result(self):
        return {
            "status": "ok",
            "signin_total": 0,
            "signin_ok": 0,
            "signin_failed": [],
            "posts_ok": 0,
            "posts_target": self.post_times,
            "post_failed": False,
        }

    def _print_summary(self, stopped=False):
        """
        Log one summary line per account: sign-in result and post count.
        """
        lines = ["", "==================== 运行汇总 ===================="]
        for name in self.account_names:
            result = self._results.get(name)
            if result is None:
                lines.append(f"{name}: 未运行")
                continue

            total = result.get("signin_total", 0)
            ok = result.get("signin_ok", 0)
            if total == 0:
                signin_text = "无签到任务"
            elif ok == total:
                signin_text = f"签到 {ok}/{total} 成功"
            elif ok > 0:
                signin_text = f"签到 {ok}/{total}，部分失败"
            else:
                signin_text = f"签到 0/{total} 失败"

            posts_ok = result.get("posts_ok", 0)
            posts_target = result.get("posts_target", self.post_times)
            post_text = f"发帖 {posts_ok}/{posts_target}"

            status = result.get("status", "ok")
            if status == "not_logged_in":
                status_text = "未登录，已停止"
            elif status == "error":
                status_text = "账号异常"
            elif result.get("post_failed"):
                status_text = "发帖失败，已跳过"
            elif posts_ok < posts_target:
                status_text = "发帖未完成"
            elif result.get("signin_failed"):
                status_text = "签到有失败"
            else:
                status_text = "正常"

            lines.append(f"{name}: {signin_text}；{post_text}；{status_text}")

        if stopped:
            lines.append("（因账号未登录，后续账号未运行）")
        lines.append("==================================================")
        logging.info("\n".join(lines))

    def post(self):
        """
        Follow the configured Chaohua and publish posts in the last one.
        """
        if not chaohua_urls:
            logging.error("chaohua_urls is empty, nothing to post.")
            return

        target_url = chaohua_urls[-1]
        target_key = target_url.rstrip("/")

        # Build the sign-in order without duplicates, and always put the
        # posting target last so it does not need to be reloaded before
        # publishing (fewer page loads means less risk of 访问频繁).
        sign_in_urls = []
        seen = set()
        target_in_sign_in = False
        for url in signin_chaohua_urls:
            key = url.rstrip("/")
            if key == target_key:
                target_in_sign_in = True
                continue
            if key in seen:
                continue
            seen.add(key)
            sign_in_urls.append(url)
        if target_in_sign_in:
            sign_in_urls.append(target_url)

        # Open the first page we are going to use anyway; this both checks
        # the login state and avoids an extra page load (the old code also
        # opened weibo.com/login.php first, which is unnecessary here).
        first_url = sign_in_urls[0] if sign_in_urls else target_url
        self._goto(first_url)
        if not self._is_logged_in():
            raise NotLoggedInError(
                f"Account '{self.account_name}' is not logged in. "
                "Please log in with login_chrome.py before posting.")

        # Follow and sign in to every configured Chaohua.  signin_chaohua_urls
        # can contain sign-in-only topics (see core/__init__.py).
        result = self._current_result
        for url in sign_in_urls:
            if url.rstrip("/") != (self.driver.current_url or "").rstrip("/"):
                self._goto(url)
            try:
                self._ensure_followed(url)
            except Exception as exc:
                logging.warning(f"Could not follow '{self._chaohua_name(url)}': {exc}")

            result["signin_total"] += 1
            try:
                if self._sign_in(url):
                    result["signin_ok"] += 1
                else:
                    result["signin_failed"].append(url)
            except NotLoggedInError:
                raise
            except Exception as exc:
                logging.warning(f"Could not sign in '{self._chaohua_name(url)}': {exc}")
                result["signin_failed"].append(url)

        # Normally the target was signed in last and is already open.
        if target_key != (self.driver.current_url or "").rstrip("/"):
            self._goto(target_url)
        self._post_loop()

    # ------------------------------------------------------------------
    # Publishing flow
    # ------------------------------------------------------------------
    def _post_loop(self):
        result = self._current_result
        result["posts_ok"] = 0
        result["post_failed"] = False
        success_count = 0
        for index in range(1, self.post_times + 1):
            try:
                textarea, root = self._open_composer()
                post_value = self._fill_composer(textarea, root)
                send_button = self._find_send_button(root)
                if send_button is None:
                    raise RuntimeError("cannot find the send button")

                self._clear_performance_log()
                logging.info(f"Publishing post {index}/{self.post_times} as '{self.account_name}' ...")
                self._click(send_button)

                status, detail = self._wait_publish_result(root)
                if status == "success":
                    success_count += 1
                    result["posts_ok"] = success_count
                    logging.info(
                        f"Post on behalf of '{self.account_name}' "
                        f"({index}/{self.post_times}): '{post_value}'"
                    )
                    # Give the feed a moment to settle before the next post.
                    sleep(4)
                    continue

                result["post_failed"] = True
                if status == "error":
                    result["post_error"] = detail
                    logging.error(f"Publishing failed: {detail}")
                    if "请先登录" in detail or "登录后" in detail:
                        self._dump_diagnostics("login-expired")
                        raise NotLoggedInError(
                            f"Weibo login has expired for account {self.account_name}. "
                            "Please log in with login_chrome.py before posting.")
                else:
                    response = self._last_publish_response()
                    result["post_error"] = response if response is not None else detail
                    if response is None:
                        logging.error(
                            "Publishing failed: no /ajax/statuses/update response was "
                            f"captured ({detail}). The send button click may have been blocked."
                        )
                    else:
                        logging.error(f"Publishing failed, API response: {response}")
                        if (response.get("ok") == -100
                                or "请先登录" in str(response.get("msg", ""))):
                            self._dump_diagnostics("login-expired")
                            raise NotLoggedInError(
                                f"Weibo login has expired for account {self.account_name}. "
                                "Please log in with login_chrome.py before posting.")
                logging.error(
                    f"Skip the remaining posts for '{self.account_name}' "
                    "and continue with the next account.")
                self._dump_diagnostics("publish-failed")
                break
            except NotLoggedInError:
                result["post_failed"] = True
                raise
            except Exception as exc:
                result["post_failed"] = True
                result["post_error"] = str(exc)
                logging.error(
                    f"Post {index} failed: {exc}; skip the remaining posts for "
                    f"'{self.account_name}' and continue with the next account.",
                    exc_info=True)
                self._dump_diagnostics("post-error")
                break

        logging.info(f"Published {success_count}/{self.post_times} post(s) as '{self.account_name}'")
        return success_count

    def _open_composer(self):
        """
        Click the "发帖" button and return ``(textarea, composer_root)``.
        Handles the "关注超话后才能发帖" dialog that the new UI shows.
        """
        last_state = None
        for attempt in range(1, 4):
            publish_button = self._wait_publish_button()
            self._click(publish_button)
            state, payload = self._wait_composer_state(timeout=10)
            last_state = state

            if state == "composer":
                return payload

            if state == "login":
                raise NotLoggedInError(
                    f"Account '{self.account_name}' is not logged in. "
                    "Please log in with login_chrome.py before posting.")

            if state == "follow":
                confirm = self._find_by_text(payload, self.FOLLOW_BUTTON_TEXTS)
                if confirm is None:
                    raise RuntimeError("follow dialog appeared but no 加关注 button was found")
                logging.info(f"Following the Chaohua before posting ('{self.account_name}')")
                self._click(confirm)
                self._wait_dialog_closed(payload, timeout=10)
                sleep(1)
                continue

            # Nothing appeared (a guide popup, an ad, a slow page, ...).
            logging.warning(f"The composer did not open (attempt {attempt}/3).")
            self._dismiss_popups()
            sleep(1)

        raise RuntimeError(f"could not open the Chaohua composer (last state: {last_state})")

    def _fill_composer(self, textarea, root):
        """
        Keep the topic prefix inserted by Weibo, append the random post,
        set the "同步到微博" checkbox and return the final text.
        """
        existing = textarea.get_attribute("value") or ""
        # The new composer pre-fills "#<topic>[超话]# ".  Keeping it makes
        # the post show up correctly in the Chaohua.
        match = re.match(r"^(#.+?\[超话\]#\s*)", existing)
        prefix = match.group(1) if match else ""
        post_value = prefix + generate_random_post()

        textarea.click()
        textarea.clear()
        if textarea.get_attribute("value"):
            # clear() is not reliable on every textarea; select-all + delete.
            textarea.send_keys(Keys.COMMAND, "a")
            textarea.send_keys(Keys.DELETE)
        textarea.send_keys(post_value)

        if not self._composer_contains(textarea, post_value):
            # Some Vue versions need an explicit input event after send_keys.
            logging.warning("The typed text was not registered, dispatching an input event")
            self.driver.execute_script(
                """
                const textarea = arguments[0];
                const value = arguments[1];
                textarea.value = value;
                textarea.dispatchEvent(new Event('input', {bubbles: true}));
                textarea.dispatchEvent(new Event('change', {bubbles: true}));
                """,
                textarea,
                post_value,
            )
            if not self._composer_contains(textarea, post_value):
                raise RuntimeError("could not write the post text into the composer")

        send_button = self._find_send_button(root)
        if send_button is None:
            raise RuntimeError("cannot find the send button in the composer")

        try:
            WebDriverWait(self.driver, 10).until(lambda _: send_button.is_enabled())
        except TimeoutException:
            raise RuntimeError("the send button stayed disabled after typing")

        self._set_sync_checkbox(root)
        sleep(1)
        return post_value

    def _set_sync_checkbox(self, root):
        """
        Make the "同步到微博" checkbox match ``SYNC_TO_WEIBO``.
        """
        label = self._first_visible(root.find_elements(By.CSS_SELECTOR, "label.woo-checkbox-main"))
        if label is None:
            logging.warning("The '同步到微博' checkbox was not found; using the current value.")
            return

        try:
            checkbox = label.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
        except WebDriverException:
            logging.warning("The '同步到微博' checkbox input was not found.")
            return

        if checkbox.is_selected() == self.SYNC_TO_WEIBO:
            return

        self._click(label)
        try:
            WebDriverWait(self.driver, 3).until(
                lambda _: checkbox.is_selected() == self.SYNC_TO_WEIBO)
        except TimeoutException:
            logging.warning("Could not change the '同步到微博' checkbox.")

    @staticmethod
    def _composer_contains(textarea, value):
        current = textarea.get_attribute("value") or ""
        return value.strip() in current or value.strip()[-30:] in current

    def _wait_publish_result(self, root, timeout=25):
        """
        Wait until the composer closes (success) or an error appears.
        """
        def check(_):
            for element in self.driver.find_elements(
                    By.CSS_SELECTOR,
                    ".woo-toast-main, .woo-toast, [class*='toast'], .woo-dialog-main"):
                try:
                    if not element.is_displayed():
                        continue
                except StaleElementReferenceException:
                    continue
                text = (element.text or "").strip()
                if not text:
                    continue
                # A "签到失败/关注失败" toast may still be on screen from
                # the steps before posting; it is not a post result.
                if "签到" in text or "关注" in text:
                    continue
                if any(keyword in text for keyword in self.SUCCESS_TEXTS):
                    return "success", text
                if any(keyword in text for keyword in self.ERROR_TEXTS):
                    return "error", text

            # The supertopic publisher emits "close" after ok > 0, so a
            # closed composer is the most reliable success signal.
            if self._composer_root() is None:
                return "success", "the composer closed"

            # If the root was passed in but replaced, re-check by textarea.
            try:
                if not root.is_displayed():
                    return "success", "the composer closed"
            except StaleElementReferenceException:
                return "success", "the composer was replaced"
            return None

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(check)
        except TimeoutException:
            return "timeout", "the composer is still open"

    # ------------------------------------------------------------------
    # Following / page helpers
    # ------------------------------------------------------------------
    def _ensure_followed(self, url):
        """
        Follow the Chaohua from its header.  If the button is not present
        (already followed, or a logged-out page), the composer's follow
        dialog is handled later by ``_open_composer``.
        """
        self._wait_publish_button(timeout=25)
        name = self._chaohua_name(url)

        state = self._follow_state()
        if state is True:
            logging.info(f"'{self.account_name}' already follows '{name}'")
            return True
        if state is None:
            logging.info(f"Follow state of '{name}' is unknown; it will be checked before posting")
            return False

        follow_button = self._find_header_follow_button()
        if follow_button is None:
            logging.warning(f"Could not find the follow button for '{name}'")
            return False

        self._click(follow_button)
        logging.info(f"Follow '{name}' as '{self.account_name}'")
        if self._wait_followed(timeout=10):
            logging.info(f"Followed '{name}'")
            return True
        logging.warning(f"Follow state for '{name}' did not change")
        return False

    def _follow_state(self):
        """
        Return True (followed), False (not followed) or None (unknown).
        """
        if self._first_visible(
                self.driver.find_elements(By.CSS_SELECTOR, "[class*='fllowedBtnOverlay']")):
            return True
        if self._first_visible(
                self.driver.find_elements(By.CSS_SELECTOR, "[class*='fllowBtnCanFollow']")):
            return False
        return None

    def _find_header_follow_button(self):
        """
        Find the "关注" button in the Chaohua header (not the follow
        buttons next to the posts in the feed).
        """
        button = self._first_visible(
            self.driver.find_elements(By.CSS_SELECTOR, "[class*='fllowBtnCanFollow']"))
        if button is not None:
            return button

        publish_button = self._wait_publish_button()
        try:
            actions = publish_button.find_element(
                By.XPATH, "./ancestor-or-self::*[contains(@class, 'publish_btn')][1]/..")
        except WebDriverException:
            actions = publish_button.find_element(By.XPATH, "./..")
        return self._find_by_text(actions, self.FOLLOW_BUTTON_TEXTS)

    def _wait_followed(self, timeout=10):
        def check(_):
            if self._first_visible(
                    self.driver.find_elements(By.CSS_SELECTOR, "[class*='fllowedBtnOverlay']")):
                return True
            if not self._first_visible(
                    self.driver.find_elements(By.CSS_SELECTOR, "[class*='fllowBtnCanFollow']")):
                return True
            return False

        try:
            return bool(WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(check))
        except TimeoutException:
            return False

    # ------------------------------------------------------------------
    # Chaohua check-in (签到)
    # ------------------------------------------------------------------
    def _sign_in(self, url):
        """
        Sign in (签到) to one Chaohua.  The new UI only renders the
        "签到" button after the account follows the Chaohua, so this is
        called after ``_ensure_followed``.  If the button is missing or
        the click does not finish, the page's own check-in API is used.
        """
        name = self._chaohua_name(url)
        button = self._wait_sign_button(timeout=5)
        if button is not None:
            text = (button.text or "").strip()
            classes = button.get_attribute("class") or ""
            if "已签到" in text or "signBtnActive" in classes:
                logging.info(f"'{self.account_name}' already signed in '{name}'")
                return True

            logging.info(f"Sign in '{name}' as '{self.account_name}'")
            self._click(button)
            status, detail = self._wait_sign_result(timeout=10)
            if status == "success":
                summary = detail.splitlines()[0] if detail else "OK"
                logging.info(f"Signed in '{name}' as '{self.account_name}': {summary}")
                self._close_sign_dialog()
                return True
            if status == "error":
                logging.warning(f"Sign-in button for '{name}' failed: {detail}")
            else:
                logging.warning(f"Sign-in button for '{name}' did not finish, trying the API")
        else:
            logging.info(f"The 签到 button is not rendered for '{name}', trying the API")

        response = self._checkin_via_api(url)
        if isinstance(response, dict) and (
                response.get("code") in (100003, "100003")
                or response.get("msg") == "请先登录"):
            raise NotLoggedInError(
                f"Account '{self.account_name}' lost its Weibo login while signing in '{name}'.")

        if self._checkin_succeeded(response):
            logging.info(f"Signed in '{name}' as '{self.account_name}' (API)")
            return True

        logging.error(f"Could not sign in '{name}' as '{self.account_name}': {response}")
        return False

    def _wait_sign_button(self, timeout=5):
        def find(_):
            button = self._first_visible(
                self.driver.find_elements(By.CSS_SELECTOR, "[class*='signBtnOverlay']"))
            if button is not None:
                return button

            # Fallback for a class-name change: the sign button sits in the
            # same header actions box as "发帖" and "关注".
            try:
                publish_button = self._wait_publish_button(timeout=2)
                actions = publish_button.find_element(
                    By.XPATH, "./ancestor-or-self::*[contains(@class, 'publish_btn')][1]/..")
                return self._find_by_text(actions, self.SIGN_BUTTON_TEXTS)
            except (RuntimeError, WebDriverException):
                return None

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(find)
        except TimeoutException:
            return None

    def _wait_sign_result(self, timeout=10):
        def check(_):
            for element in self.driver.find_elements(
                    By.CSS_SELECTOR,
                    ".woo-dialog-main, .woo-modal-main, [role='dialog'], [class*='toast']"):
                try:
                    if not element.is_displayed():
                        continue
                except StaleElementReferenceException:
                    continue
                text = (element.text or "").strip()
                if not text:
                    continue
                if any(keyword in text for keyword in self.SIGN_SUCCESS_TEXTS):
                    return "success", text
                if any(keyword in text for keyword in self.SIGN_ERROR_TEXTS):
                    return "error", text

            button = self._first_visible(
                self.driver.find_elements(By.CSS_SELECTOR, "[class*='signBtnOverlay']"))
            if button is not None:
                text = (button.text or "").strip()
                classes = button.get_attribute("class") or ""
                if "已签到" in text or "signBtnActive" in classes:
                    return "success", "the button now shows 已签到"
            return None

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(check)
        except TimeoutException:
            return "timeout", "no sign-in result"

    def _close_sign_dialog(self):
        """
        Close the "签到成功" modal so it does not block the 发帖 button.
        """
        for element in self.driver.find_elements(
                By.CSS_SELECTOR, ".woo-dialog-main, .woo-modal-main, [role='dialog']"):
            try:
                if not element.is_displayed():
                    continue
                text = element.text or ""
                if "签到成功" not in text and "已签到" not in text:
                    continue
                button = self._find_by_text(element, ("确认", "我知道了", "知道了", "关闭"))
                if button is not None:
                    self._click(button)
                    sleep(0.5)
                    return
            except StaleElementReferenceException:
                continue

        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except WebDriverException:
            pass

    def _chaohua_name(self, url):
        """
        Return the display name for a Chaohua URL.  Uses the mapping in
        core/__init__.py first, then the page title, then the URL itself.
        """
        key = (url or "").rstrip("/")
        if key in self._chaohua_name_cache:
            return self._chaohua_name_cache[key]

        name = chaohua_names.get(url) or chaohua_names.get(key)
        if not name:
            try:
                title = self.driver.title or ""
            except (AttributeError, WebDriverException):
                title = ""
            if "超话" in title:
                name = title.split("超话")[0].strip()
        if not name:
            name = url

        self._chaohua_name_cache[key] = name
        return name

    def _checkin_via_api(self, url):
        """
        Call the same check-in endpoint as the new Chaohua page:
        POST /ajax_proxy/chaohua/page/checkin
        """
        name = self._chaohua_name(url)
        page_id = self._page_id_from_url(url)
        if not page_id:
            logging.warning(f"Cannot read the Chaohua page id from '{name}'")
            return None

        script = """
        const done = arguments[arguments.length - 1];
        const pageId = arguments[0];
        const cookie = document.cookie.split('; ').find(item => item.startsWith('XSRF-TOKEN='));
        const xsrf = cookie ? decodeURIComponent(cookie.substring('XSRF-TOKEN='.length)) : '';
        const body = new URLSearchParams({
            scene_id: 'pc_checkin',
            page_id: pageId,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            lang: navigator.language || 'zh-cn',
            plat: navigator.platform,
            ua: navigator.userAgent
        }).toString();
        fetch('/ajax_proxy/chaohua/page/checkin', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'X-XSRF-TOKEN': xsrf
            },
            body: body
        }).then(response => response.text().then(text => done({status: response.status, body: text})))
          .catch(error => done({error: String(error)}));
        """
        try:
            result = self.driver.execute_async_script(script, page_id)
        except WebDriverException as exc:
            logging.warning(f"Check-in API call failed for '{name}': {exc}")
            return None

        if not isinstance(result, dict) or "body" not in result:
            logging.warning(f"Check-in API call for '{name}' returned no body: {result}")
            return None
        try:
            return json.loads(result["body"])
        except (TypeError, ValueError):
            return {"raw": str(result["body"])[:300]}

    @staticmethod
    def _checkin_succeeded(response):
        if not isinstance(response, dict):
            return False
        if response.get("code") in (100000, "100000"):
            return True
        text = " ".join(
            str(response.get(key, "")) for key in ("msg", "title", "sub_title"))
        return "签到成功" in text or "已签到" in text

    def _page_id_from_url(self, url):
        match = re.search(r"/p/(100808[0-9a-fA-F]+)", url or "")
        if match:
            return match.group(1)
        match = re.search(r"/p/(100808[0-9a-fA-F]+)", self.driver.current_url or "")
        return match.group(1) if match else None

    def _goto(self, url):
        self.driver.get(url)
        try:
            WebDriverWait(self.driver, 30).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete")
        except TimeoutException:
            pass
        sleep(2)

    def _wait_publish_button(self, timeout=25):
        def find(driver):
            # The header is server-rendered before Vue hydrates; clicking a
            # button during that window does nothing.
            try:
                mounted = driver.execute_script(
                    "const app = document.querySelector('#app'); "
                    "return !app || !!app.__vue_app__;")
            except WebDriverException:
                mounted = True
            if not mounted:
                return False

            button = self._find_by_text(driver, self.PUBLISH_BUTTON_TEXTS)
            if button is not None:
                return button
            return self._first_visible(
                driver.find_elements(By.CSS_SELECTOR, "[class*='publish_btn']"))

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(find)
        except TimeoutException:
            raise RuntimeError("could not find the 发帖 button; the page may not have loaded")

    def _composer_root(self):
        return self._first_visible(self.driver.find_elements(By.CSS_SELECTOR, ".wbpro-layer"))

    def _wait_composer_state(self, timeout=10):
        """
        Wait for the composer or for one of the dialogs that can appear
        before it.  Returns ``("composer", (textarea, root))``,
        ``("follow", dialog)``, ``("login", None)`` or ``("timeout", None)``.
        """
        def check(_):
            root = self._composer_root()
            if root is not None:
                textarea = self._find_composer_textarea(root)
                if textarea is not None:
                    return "composer", (textarea, root)

            follow_dialog = self._visible_dialog(self.FOLLOW_DIALOG_TEXT)
            if follow_dialog is not None:
                return "follow", follow_dialog

            if self._visible_login_dialog():
                return "login", None
            return None

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(check)
        except TimeoutException:
            return "timeout", None

    def _find_composer_textarea(self, root):
        textarea = self._first_visible(root.find_elements(By.TAG_NAME, "textarea"))
        if textarea is not None:
            return textarea
        # Fallback for a composer rendered in another portal.
        textarea = self._first_visible(
            self.driver.find_elements(By.CSS_SELECTOR, "textarea[placeholder*='此贴必火']"))
        return textarea

    def _find_send_button(self, root):
        condition = " or ".join(
            f"normalize-space(.)='{text}'" for text in self.SEND_BUTTON_TEXTS)
        buttons = root.find_elements(By.XPATH, f".//button[{condition}]")
        button = self._first_visible(buttons)
        if button is not None:
            return button

        # The send button is the last visible primary button of the composer.
        buttons = [button for button in root.find_elements(
            By.CSS_SELECTOR, "button.woo-button-primary") if self._is_displayed(button)]
        return buttons[-1] if buttons else None

    def _visible_dialog(self, keyword):
        for element in self.driver.find_elements(
                By.CSS_SELECTOR,
                ".woo-dialog-main, .woo-modal-main, [role='dialog'], [class*='woo-dialog']"):
            try:
                if element.is_displayed() and keyword in (element.text or ""):
                    return element
            except StaleElementReferenceException:
                continue
        return None

    def _visible_login_dialog(self):
        for element in self.driver.find_elements(
                By.CSS_SELECTOR,
                ".woo-dialog-main, .woo-modal-main, [role='dialog'], [class*='woo-dialog']"):
            try:
                if not element.is_displayed():
                    continue
                text = (element.text or "").strip()
                if not text:
                    continue
                if "扫码登录" in text or "请先登录" in text or "登录后" in text:
                    return True
            except StaleElementReferenceException:
                continue
        return False

    def _wait_dialog_closed(self, dialog, timeout=10):
        try:
            WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(
                lambda _: not self._is_displayed(dialog))
        except (TimeoutException, StaleElementReferenceException):
            pass

    def _dismiss_popups(self):
        for text in ("我知道了", "知道了", "确认", "取消"):
            try:
                button = self._find_by_text(self.driver, (text,))
                if button is not None:
                    self._click(button)
                    sleep(0.5)
            except WebDriverException:
                continue
        # Close an unexpected composer so the next attempt starts clean.
        root = self._composer_root()
        if root is not None:
            try:
                close_button = root.find_element(By.CSS_SELECTOR, ".wbpro-layer-tit-opt")
                self._click(close_button)
                sleep(1)
            except WebDriverException:
                pass

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------
    def _is_logged_in(self):
        try:
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script("return !!window.$CONFIG"))
            return bool(self.driver.execute_script(
                "return !!(window.$CONFIG && (window.$CONFIG.user || window.$CONFIG.uid))"))
        except (TimeoutException, WebDriverException):
            return False

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

    @classmethod
    def _find_by_text(cls, root, texts):
        condition = " or ".join(f"normalize-space(.)='{text}'" for text in texts)
        xpath = (
            f".//*[self::button or self::a or self::div or self::span or self::li][{condition}]")
        return cls._first_visible(root.find_elements(By.XPATH, xpath))

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

    def _clear_performance_log(self):
        try:
            self.driver.get_log("performance")
        except WebDriverException:
            pass

    def _last_publish_response(self):
        """
        Read the JSON returned by /ajax/statuses/update from the browser
        performance log.  Used only for diagnostics.
        """
        try:
            logs = self.driver.get_log("performance")
        except WebDriverException:
            return None

        request_id = None
        for entry in reversed(logs):
            try:
                message = json.loads(entry["message"])["message"]
            except (ValueError, KeyError, TypeError):
                continue
            if message.get("method") != "Network.responseReceived":
                continue
            params = message.get("params", {})
            url = params.get("response", {}).get("url", "")
            if "/ajax/statuses/update" in url:
                request_id = params.get("requestId")
                break

        if request_id is None:
            return None
        try:
            body = self.driver.execute_cdp_cmd(
                "Network.getResponseBody", {"requestId": request_id})
            text = body.get("body", "")
            if body.get("base64Encoded"):
                text = b64decode(text).decode("utf-8", "replace")
            return json.loads(text)
        except (WebDriverException, ValueError):
            return None

    def _dump_diagnostics(self, tag):
        if self.driver is None:
            return
        try:
            os.makedirs("log", exist_ok=True)
            safe_account = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_.-]+", "_", self.account_name or "unknown")
            base = f"log/chaohua-{safe_account}-{tag}-{strftime('%Y%m%d-%H%M%S')}"
            self.driver.save_screenshot(f"{base}.png")
            with open(f"{base}.html", "w", encoding="utf-8") as file:
                file.write(self.driver.page_source)
            logging.info(f"Saved diagnostics to {base}.png and {base}.html")
        except Exception as exc:  # diagnostics must never hide the real error
            logging.warning(f"Could not save diagnostics: {exc}")

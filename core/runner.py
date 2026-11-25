"""
Command-line runner for the three Weibo features.
"""
import argparse
import logging
import sys

import config
from core.forward_weibo import WeiboForwarder
from core.post_in_chaohua import WeiboPoster
from core.send_comment import CommentSender
from core.targets import DATA_FILES, ensure_weibo_target, get_last_target
from core.util import get_start_info

MODES = {
    "comment": "微博评论",
    "forward": "微博转发",
    "chaohua": "超话发帖",
}


ACCOUNT_SETTINGS = {
    "comment": "COMMENT_ACCOUNTS",
    "forward": "FORWARD_ACCOUNTS",
    "chaohua": "CHAOHUA_ACCOUNTS",
}


def _accounts(mode):
    setting = ACCOUNT_SETTINGS[mode]
    accounts = list(getattr(config, setting, None) or [])
    if not accounts:
        raise RuntimeError(f"config.py 中的 {setting} 为空，请先配置账号。")

    missing = [name for name in accounts if name not in config.ACCOUNTS]
    if missing:
        raise KeyError(
            f"{setting} 中的账号 {missing} 未在 ACCOUNTS (config.py) 中定义。")
    return accounts


def _resolve_link(mode, link=None):
    """
    Return the target link: command line > config.py > prompt / last target.
    """
    link = (link or "").strip()
    if link:
        return link

    configured = config.COMMENT_LINK if mode == "comment" else config.FORWARD_LINK
    configured = (configured or "").strip()
    if configured:
        return configured

    last_link = get_last_target(mode)
    if not sys.stdin.isatty():
        raise RuntimeError(
            f"未配置 {mode} 目标链接；请在 config.py 中填写，"
            f"或使用 --link 参数。")

    prompt = f"请输入要{'评论' if mode == 'comment' else '转发'}的微博链接"
    if last_link:
        prompt += f"（直接回车使用上次：{last_link}）"
    prompt += ": "
    entered = input(prompt).strip()
    if entered:
        return entered
    if last_link:
        return last_link
    raise RuntimeError("未输入微博链接，已取消。")


def run_mode(mode, link=None):
    """
    Run one feature.

    :param mode: "comment" | "forward" | "chaohua"
    :param link: optional target Weibo link (comment/forward only)
    """
    mode = (mode or "").strip().lower()
    if mode not in MODES:
        raise ValueError(f"未知功能: {mode}（可选: {', '.join(MODES)}）")

    accounts = _accounts(mode)

    if mode in ("comment", "forward"):
        target_link = _resolve_link(mode, link)
        index, target, created = ensure_weibo_target(mode, target_link)
        if created:
            logging.info(
                f"新目标已写入 {DATA_FILES[mode]}：{target['link']} "
                f"（序号从 0 开始）")
        else:
            logging.info(
                f"使用已有目标：{target['tag']} | "
                f"当前序号 {target['total_comment_count']}")

        get_start_info(accounts, index, mode)
        if mode == "comment":
            CommentSender(accounts, index).run()
        else:
            WeiboForwarder(accounts, index).run()
        return

    if link:
        logging.warning("超话发帖不使用 --link，已忽略目标链接。")
    logging.info(
        f"Start Chaohua posting | {len(accounts)} accounts | "
        f"{config.CHAOHUA_POST_TIMES} posts/account ...")
    WeiboPoster(accounts).run()


def build_parser():
    parser = argparse.ArgumentParser(
        description="微博自动化：评论 / 转发 / 超话发帖",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python main.py comment\n"
            "  python main.py forward\n"
            "  python main.py chaohua\n"
        ),
    )
    parser.add_argument(
        "mode", nargs="?", choices=tuple(MODES),
        help="要运行的功能：comment / forward / chaohua")
    parser.add_argument(
        "link", nargs="?", help="目标微博链接（评论/转发；新链接会自动加入统计）")
    parser.add_argument(
        "--link", dest="link_option", help="目标微博链接（评论/转发）")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    link = args.link_option or args.link

    if not args.mode:
        parser.print_help()
        return 1

    try:
        run_mode(args.mode, link)
    except KeyboardInterrupt:
        logging.warning("已中断。")
        return 1
    except Exception as exc:
        logging.error(f"运行失败: {exc}", exc_info=True)
        return 1
    return 0

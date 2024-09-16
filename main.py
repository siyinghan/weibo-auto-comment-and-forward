"""
Login with different Weibo accounts.
"""
from core.forward_weibo import WeiboForwarder
from core.post_in_chaohua import WeiboPoster
from core.send_comment import CommentSender
from core.util import get_start_info

accounts = ["account 1", "account 2", "account 3"]
link_index = 0

if __name__ == "__main__":
    # get_start_info(accounts, link_index, "comment")
    # CommentSender(accounts, link_index).run()
    # get_start_info(accounts, link_index, "forward")
    # WeiboForwarder(accounts, link_index).run()
    WeiboPoster(accounts).run()

"""
Login with different Weibo accounts.
"""
from core.forward_weibo import WeiboForwarder
from core.post_in_chaohua import WeiboPoster
from core.send_comment import CommentSender
from core.util import get_start_info

# accounts = ["太阳", "舔狗", "卷卷", "big_414", "啊大777", "喵啊啊", "TTTTTS13"]
# accounts = ["舔狗", "卷卷", "big_414", "啊大777", "喵啊啊", "TTTTTS13"]
accounts = ["TTTTTS13", "喵啊啊", "啊大777", "big_414", "卷卷", "舔狗", "太阳"]
link_index = 0

if __name__ == "__main__":
    # get_start_info(accounts, link_index, "comment")
    # CommentSender(accounts, link_index).run()
    # get_start_info(accounts, link_index, "forward")
    # WeiboForwarder(accounts, link_index).run()
    WeiboPoster(accounts).run()

"""
Login with different Weibo accounts.
"""
from util import CommentSender, get_start_info

accounts = ["account 1", "account 2", "account 3"]
link_index = 0

if __name__ == "__main__":
    # copy files from the storage
    get_start_info(accounts, link_index)
    CommentSender(accounts, link_index).run()

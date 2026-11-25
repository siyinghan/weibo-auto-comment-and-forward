"""
Save login information in the Chrome profile.
"""
from core.login import Login

# fill in an account name defined in config.py ACCOUNTS
account_name = "xxx"

if __name__ == "__main__":
    Login().run_chrome(account_name)

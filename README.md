# weibo-auto-comment

## Quickstart

### Preparation

Need to install Chrome in advance.

Chrome profile folder:

```zsh
$ open ~/Library/Application\ Support/Google/Chrome
```

### Chrome Login

1. Create Weibo accounts information file.
    1. Create an empty `json` file in the project **resources** folder.
       ```zsh
       $ touch resources/accounts.json
       ```
    2. Fill in the account names, the accordant profile names,
       and the number that the account can comment (**20** in the example).
       ```json
       {
         "account name 1": [
           "profile name 1",
           20
         ],
         "account name 2": [
           "profile name 2",
           20
         ]
       }
       ```

2. Fill in the `account_name` instead of "xxx" in `login_chrome.py`, then run `login_chrome.py` to log in.
   ```zsh
   $ python login_chrome.py
   ```

3. Scan the QR code in the automated browser to save the login information.

### Create comments data file

1. Create an empty `json` file in the project **resources** folder:
   ```zsh
   $ touch resources/data.json
   ```

2. Add a dictionary in the list of ***weibo_details*** when there is a new Weibo that needs comments.
   Following is the example.
    - ***link***: link to the Weibo
    - ***comment_count***: always put **0** for a new Weibo (will be updated automatically)
    - ***tag***: could be anything
    - ***index***: add **1** every time for a new Weibo

   ```json
   {
     "weibo_details": [
       {
         "link": "",
         "total_comment_count": 0,
         "tag": "",
         "index": 0
       },
       {
         "link": "",
         "total_comment_count": 0,
         "tag": "",
         "index": 1
       }
     ]
   }
   ```

### Send comments and like

1. Replace the account names (should be the same names as in `resources/accounts.json`)
   in `main.py` *accounts = ["account 1", "account 2", "account 3"]*.

2. Start comments and like.
   ```zsh
   $ python main.py
   ```
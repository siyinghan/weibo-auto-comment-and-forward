"""
项目统一配置。

日常只需要修改这个文件，不需要再改 main.py。
运行方式：
    python main.py comment
    python main.py forward
    python main.py chaohua
"""

# ======================================================================
# 1. 账号
# ======================================================================
# 格式：账号名: Chrome Profile 名称
# 账号名会出现在日志和汇总里；Profile 名称必须和 Chrome 里的目录名一致。
# 当前按 Profile 1 → 11 排序（Profile 6 / 9 没有账号）。
ACCOUNTS = {
    "汐琊": "Profile 1",
    "太阳": "Profile 2",
    "xyhhlx": "Profile 3",
    "月夕花晨": "Profile 4",
    "舔狗": "Profile 5",
    "big_414": "Profile 7",
    "啊大777": "Profile 8",
    "喵啊啊": "Profile 10",
    "TTTTTS13": "Profile 11",
}

# 三个功能分别使用哪些账号（从上面的 ACCOUNTS 里选，顺序就是运行顺序）。
# 三个列表可以完全不同；想临时停用某个账号，从对应列表里删掉即可。
# 账号必须先在上面的 ACCOUNTS 中定义好 Profile。
COMMENT_ACCOUNTS = [
    "汐琊",
    "太阳",
    "xyhhlx",
    "月夕花晨",
    "舔狗",
    "big_414",
    "啊大777",
    "喵啊啊",
    "TTTTTS13",
]
FORWARD_ACCOUNTS = [
    "太阳",
    "xyhhlx",
    "月夕花晨",
    "舔狗",
    "big_414",
    "啊大777",
    "喵啊啊",
    "TTTTTS13",
]
CHAOHUA_ACCOUNTS = [
    "太阳",
    "xyhhlx",
    "月夕花晨",
    "舔狗",
    "big_414",
    "啊大777",
    "喵啊啊",
    "TTTTTS13",
]

# ======================================================================
# 2. 微博评论
# ======================================================================
# 换成一个新链接后运行，会自动写入 conf/comment_data.json，序号从 0 开始。
# 留空则运行时提示输入；也可以在命令行用 --link 临时指定。
COMMENT_LINK = "https://weibo.com/2172061270/RsJ4Vt6JR"
COMMENTS_PER_ACCOUNT = 25

# ======================================================================
# 3. 微博转发
# ======================================================================
# 换成一个新链接后运行，会自动写入 conf/forward_data.json，序号从 0 开始。
# 留空则运行时提示输入；也可以在命令行用 --link 临时指定。
FORWARD_LINK = "https://weibo.com/1677178177/MxQDsqOWu"
FORWARDS_PER_ACCOUNT = 25

# ======================================================================
# 4. 超话发帖 / 签到
# ======================================================================
# 超话：暗河传、白衣公卿、凤舞九天、豹隐南山、龚俊温客行、龚俊
CHAOHUA_URLS = [
    "https://weibo.com/p/100808241b9ceecb561bd8de83d5e2f69b3beb",
    "https://weibo.com/p/10080837b798d2cfac00077133b309f2aac540",
    "https://weibo.com/p/10080894303e1cc6c5cef797640704c240fcfb",
    "https://weibo.com/p/1008083ce145cd2ed223247b5803187777c2b6",
    "https://weibo.com/p/100808d3fa73b65abd6f2e91cf143c1726319f",
    "https://weibo.com/p/100808b503e94e4f2f272c6e1cf79b59c41085",
]

# 超话名称：只用于日志显示。新增超话链接时，在这里补一个名字即可。
CHAOHUA_NAMES = {
    "https://weibo.com/p/100808241b9ceecb561bd8de83d5e2f69b3beb": "暗河传",
    "https://weibo.com/p/10080837b798d2cfac00077133b309f2aac540": "白衣公卿",
    "https://weibo.com/p/10080894303e1cc6c5cef797640704c240fcfb": "凤舞九天",
    "https://weibo.com/p/1008083ce145cd2ed223247b5803187777c2b6": "豹隐南山",
    "https://weibo.com/p/100808d3fa73b65abd6f2e91cf143c1726319f": "龚俊温客行",
    "https://weibo.com/p/100808b503e94e4f2f272c6e1cf79b59c41085": "龚俊",
}

# 需要签到的超话列表；默认与 CHAOHUA_URLS 相同。
# 只签到、不发帖的超话，直接追加到这里。
SIGNIN_CHAOHUA_URLS = list(CHAOHUA_URLS)

# 每个账号每次发几条超话帖子。
CHAOHUA_POST_TIMES = 6
# 是否把超话帖子同步到个人微博（False = 只发超话）。
CHAOHUA_SYNC_TO_WEIBO = False
# 超话帖子使用的固定前缀和链接。
CHAOHUA_PRE_POST_TEXT = "#龚俊# 俊味仙 #龚俊孟剑卿# ｜#龚俊白衣公卿#"
CHAOHUA_POST_LINK = "https://video.weibo.com/show?fid=1034:5249538768699394"

# ======================================================================
# 5. 其他
# ======================================================================
# 评论/转发账号之间的等待秒数；测试期间为 0，出现“访问频繁”可调大。
COMMENT_FORWARD_SWITCH_DELAY = 0
# 超话发帖账号之间的等待秒数。
CHAOHUA_SWITCH_DELAY = 180

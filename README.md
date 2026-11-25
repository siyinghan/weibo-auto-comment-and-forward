# weibo-auto-comment

微博自动化项目，包含三个功能：

- **微博评论**：给指定微博评论，并给自己的评论点赞。
- **微博转发**：转发指定微博并附上随机文案。
- **超话发帖**：关注/签到超话并在超话中发帖。

## 1. 环境准备

```zsh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

需要提前安装 Chrome。

## 2. 首次登录

1. 在项目根目录的 `config.py` 中配置账号和 Chrome Profile：
   ```python
   ACCOUNTS = {
       "TTTTTS13": "Profile 11",
       "喵啊啊": "Profile 10",
       # ...
   }
   ```
   - 字典的 key 是账号名，会显示在日志和汇总里。
   - value 是 Chrome Profile 目录名，例如 `Profile 11`。
   - 三个功能分别使用哪些账号，由下面的 `COMMENT_ACCOUNTS`、`FORWARD_ACCOUNTS`、`CHAOHUA_ACCOUNTS` 决定。

2. 修改 `login_chrome.py` 里的 `account_name`，填入 `config.py` 中已有的账号名：
   ```python
   account_name = "TTTTTS13"
   ```

3. 运行登录脚本，扫码登录：
   ```zsh
   python login_chrome.py
   ```

## 3. 日常配置：只改 `config.py`

所有需要手动修改的配置都在项目根目录的 [config.py](config.py)：

```python
# 账号 -> Chrome Profile（总表，只在这里维护 Profile）
ACCOUNTS = {
    "TTTTTS13": "Profile 11",
    "喵啊啊": "Profile 10",
    "月夕花晨": "Profile 4",
    "xyhhlx": "Profile 3",
    # ...
}

# 三个功能分别使用哪些账号（从 ACCOUNTS 里选，顺序就是运行顺序）
COMMENT_ACCOUNTS = ["TTTTTS13", "喵啊啊", "月夕花晨"]
FORWARD_ACCOUNTS = ["喵啊啊", "xyhhlx"]
CHAOHUA_ACCOUNTS = ["TTTTTS13", "月夕花晨", "xyhhlx"]

# 评论
COMMENT_LINK = "https://weibo.com/..."
COMMENTS_PER_ACCOUNT = 25

# 转发
FORWARD_LINK = "https://weibo.com/..."
FORWARDS_PER_ACCOUNT = 25

# 超话发帖
CHAOHUA_POST_TIMES = 6
CHAOHUA_SYNC_TO_WEIBO = False
CHAOHUA_SWITCH_DELAY = 180

# 评论/转发账号之间是否等待
COMMENT_FORWARD_SWITCH_DELAY = 0
```

### 给三个功能分配不同账号

只需要改 `config.py` 里的三个列表：

```python
COMMENT_ACCOUNTS = ["喵啊啊", "big_414"]
FORWARD_ACCOUNTS = ["太阳", "xyhhlx"]
CHAOHUA_ACCOUNTS = ["TTTTTS13", "月夕花晨"]
```

- 列表里的名字必须已经在 `ACCOUNTS` 中定义。
- 同一个账号可以出现在多个列表中。
- 某个功能暂时不想跑某个账号，从对应列表里删掉即可。
- 列表顺序就是账号运行顺序。

修改 `COMMENT_LINK` 或 `FORWARD_LINK` 为一条新微博链接后直接运行即可。程序会自动把新链接加入对应的 `conf/comment_data.json` / `conf/forward_data.json`，序号从 0 开始统计。

不再需要手动维护 `link_index`，也不需要手动编辑数据 JSON。

## 4. 运行

```zsh
python main.py comment
python main.py forward
python main.py chaohua
```

### 临时指定或新增微博链接

除了修改 `config.py` 里的 `COMMENT_LINK` / `FORWARD_LINK`，也可以在命令行直接指定链接。新链接会自动写入对应的 `conf/comment_data.json` / `conf/forward_data.json`，序号从 0 开始：

```zsh
python main.py comment --link https://weibo.com/...
python main.py forward --link https://weibo.com/...
```

也可以把链接直接放在功能名后面：

```zsh
python main.py comment https://weibo.com/...
python main.py forward https://weibo.com/...
```

## 5. 数据文件和统计

- 评论目标：`conf/comment_data.json`
- 转发目标：`conf/forward_data.json`

这两个文件由程序自动管理。每条目标包含：

```json
{
  "link": "https://weibo.com/...",
  "total_comment_count": 0,
  "tag": "自动添加 2026-11-23 20:57",
  "index": 27
}
```

- `link`：目标微博链接。
- `total_comment_count`：已成功评论/转发的序号；新链接从 0 开始。
- `tag`：日志中显示的标签。
- `index`：数据文件里的展示序号，不再需要手动设置。

已经存在的同一个微博（即使链接带 `#comment`、`#repost` 或跟踪参数）会自动匹配，不会重复添加。

每次运行结束会输出汇总，例如：

```text
==================== 运行汇总 ====================
TTTTTS13: 评论 25/25；正常
喵啊啊: 评论 18/25；触发微博限制，已跳过
合计: 评论 43/50
==================================================
```

实际数量可能少于目标：触发微博限制、未登录或页面异常时会立即结束当前账号，进入下一个账号。

## 6. 注意事项

- 请在项目根目录执行命令，保证 `conf/`、`resources/` 等相对路径可用。
- 登录状态来自 Chrome Profile；如果日志提示未登录，请用 `login_chrome.py` 重新扫码。
- 评论和转发目前账号之间不等待（`COMMENT_FORWARD_SWITCH_DELAY = 0`）。如果出现“访问频繁”，把它调大即可。
- 超话发帖的账号间隔由 `CHAOHUA_SWITCH_DELAY` 控制，默认 180 秒。

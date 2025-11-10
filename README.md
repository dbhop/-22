# Twitter 高级搜索爬虫

一个基于 Selenium 的 Twitter 爬虫工具，使用 Twitter 的高级搜索功能来爬取指定用户的所有帖子。

## 功能特点

- ✅ 使用 Twitter 高级搜索功能
- ✅ 支持爬取指定用户的所有帖子
- ✅ 支持日期范围过滤
- ✅ 自动滚动加载更多内容
- ✅ 提取完整的推文数据（文本、时间、互动数据等）
- ✅ 支持保存为 JSON 和 CSV 格式
- ✅ Cookie 持久化，避免重复登录
- ✅ 详细的日志记录

## 环境要求

- Python 3.8+
- Chrome 浏览器
- ChromeDriver（自动下载）

## 安装

1. 克隆仓库：
```bash
git clone <repository-url>
cd -22
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量（可选）：
```bash
cp .env.example .env
# 编辑 .env 文件进行配置
```

## 使用方法

### 基本用法

爬取指定用户的推文：

```bash
python twitter_crawler.py elonmusk
```

### 高级用法

```bash
# 指定滚动次数（更多滚动=更多推文）
python twitter_crawler.py elonmusk --max-scrolls 20

# 指定日期范围
python twitter_crawler.py elonmusk --since 2024-01-01 --until 2024-12-31

# 使用无头模式（不显示浏览器窗口）
python twitter_crawler.py elonmusk --headless

# 指定输出文件名
python twitter_crawler.py elonmusk --output-json my_tweets.json --output-csv my_tweets.csv

# 指定 cookies 文件
python twitter_crawler.py elonmusk --cookies my_cookies.json

# 组合使用
python twitter_crawler.py elonmusk --max-scrolls 50 --since 2024-01-01 --headless
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `username` | 要爬取的 Twitter 用户名（不含@） | **必填** |
| `--max-scrolls` | 最大滚动次数，数字越大爬取越多 | 10 |
| `--since` | 开始日期 (YYYY-MM-DD) | 无 |
| `--until` | 结束日期 (YYYY-MM-DD) | 无 |
| `--headless` | 使用无头模式（不显示浏览器） | False |
| `--cookies` | Cookies 文件路径 | twitter_cookies.json |
| `--output-json` | 输出 JSON 文件名 | tweets_时间戳.json |
| `--output-csv` | 输出 CSV 文件名 | tweets_时间戳.csv |

## 工作流程

1. **初始化浏览器**：启动 Chrome 浏览器（可选无头模式）
2. **加载 Cookies**：如果存在 cookies 文件，自动加载以保持登录状态
3. **构建搜索 URL**：根据用户名和日期范围构建 Twitter 高级搜索 URL
4. **访问搜索页面**：使用 Selenium 访问搜索结果页面
5. **登录检查**：如果需要登录，提示用户手动登录并保存 cookies
6. **滚动加载**：自动滚动页面以加载更多推文
7. **数据提取**：从每条推文中提取以下信息：
   - 用户名
   - 推文文本
   - 发布时间
   - 推文 URL 和 ID
   - 回复数
   - 转推数
   - 点赞数
8. **去重保存**：自动去除重复推文，保存为 JSON 和 CSV 格式

## 数据格式

### JSON 格式示例

```json
[
  {
    "username": "用户名",
    "text": "推文内容",
    "timestamp": "2024-01-01T12:00:00.000Z",
    "url": "https://twitter.com/username/status/1234567890",
    "tweet_id": "1234567890",
    "replies": "10",
    "retweets": "20",
    "likes": "100"
  }
]
```

### CSV 格式

CSV 文件包含相同的字段，每行一条推文。

## 首次使用注意事项

1. **首次运行需要登录**：
   - 第一次运行时，程序会打开 Twitter 登录页面
   - 手动完成登录后，按 Enter 键继续
   - 程序会自动保存 cookies，下次运行时无需再次登录

2. **ChromeDriver**：
   - 程序会自动下载匹配你 Chrome 版本的 ChromeDriver
   - 无需手动下载

3. **反爬虫限制**：
   - Twitter 有反爬虫机制，建议适当控制爬取速度
   - 不要设置过大的 `--max-scrolls` 值
   - 可以分批爬取，使用 `--since` 和 `--until` 参数

## 代码示例

如果你想在代码中使用爬虫：

```python
from twitter_crawler import TwitterCrawler

# 创建爬虫实例
crawler = TwitterCrawler(headless=False, cookies_file='twitter_cookies.json')

# 爬取推文
tweets = crawler.crawl_user_tweets(
    username='elonmusk',
    max_scrolls=20,
    since='2024-01-01',
    until='2024-12-31'
)

# 保存数据
crawler.save_to_json('my_tweets.json')
crawler.save_to_csv('my_tweets.csv')

# 输出结果
print(f"共爬取 {len(tweets)} 条推文")
for tweet in tweets[:5]:  # 显示前5条
    print(f"{tweet['timestamp']}: {tweet['text'][:50]}...")
```

## 常见问题

### 1. 如何爬取更多推文？

增加 `--max-scrolls` 参数的值：
```bash
python twitter_crawler.py username --max-scrolls 50
```

### 2. 爬取速度太慢怎么办？

- 使用无头模式：`--headless`
- 减少滚动暂停时间（需要修改代码中的 `scroll_pause` 参数）

### 3. 被 Twitter 限制了怎么办？

- 降低爬取频率
- 使用多个账号轮换
- 分时段爬取
- 使用代理 IP（需要修改代码）

### 4. Cookies 失效了怎么办？

删除 `twitter_cookies.json` 文件，重新运行程序并登录。

### 5. 如何爬取特定时间段的推文？

使用 `--since` 和 `--until` 参数：
```bash
python twitter_crawler.py username --since 2024-01-01 --until 2024-01-31
```

## 注意事项

⚠️ **重要提示**：

1. **遵守 Twitter 服务条款**：使用爬虫需遵守 Twitter 的服务条款和 robots.txt 规则
2. **合理使用**：不要频繁爬取，避免给 Twitter 服务器造成过大压力
3. **个人学习使用**：本工具仅供学习和研究使用，请勿用于商业目的
4. **数据隐私**：爬取的数据仅限个人使用，不要泄露他人隐私信息
5. **账号安全**：建议使用小号进行爬取，避免主账号被封禁

## 技术架构

- **Selenium**：浏览器自动化框架
- **Chrome WebDriver**：Chrome 浏览器驱动
- **Python 3**：主要编程语言

## 项目结构

```
.
├── twitter_crawler.py      # 主爬虫程序
├── requirements.txt         # Python 依赖包
├── .env.example            # 环境变量示例
├── .gitignore              # Git 忽略文件
├── README.md               # 使用说明
└── twitter_cookies.json    # Cookies 文件（首次登录后生成）
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 更新日志

### v1.0.0 (2024-01-01)
- 初始版本
- 实现基于 Twitter 高级搜索的爬虫功能
- 支持日期范围过滤
- 支持 JSON 和 CSV 导出
- Cookie 持久化

## 联系方式

如有问题，请提交 Issue。

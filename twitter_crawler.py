#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Twitter高级搜索爬虫
通过Twitter的高级搜索功能爬取指定用户的所有帖子
"""

import time
import json
import csv
import os
from datetime import datetime
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('twitter_crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TwitterCrawler:
    """Twitter爬虫类"""

    def __init__(self, headless: bool = False, cookies_file: str = None):
        """
        初始化爬虫

        Args:
            headless: 是否使用无头模式
            cookies_file: cookies文件路径，用于保持登录状态
        """
        self.headless = headless
        self.cookies_file = cookies_file
        self.driver = None
        self.tweets_data = []

    def _setup_driver(self) -> webdriver.Chrome:
        """设置Chrome驱动"""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument('--headless')

        # 通用设置
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_argument('--lang=zh-CN')

        # 禁用图片加载以提高速度（可选）
        # prefs = {"profile.managed_default_content_settings.images": 2}
        # chrome_options.add_experimental_option("prefs", prefs)

        # 使用webdriver-manager自动管理ChromeDriver
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            logger.warning(f"使用webdriver-manager失败: {e}, 尝试使用系统ChromeDriver")
            driver = webdriver.Chrome(options=chrome_options)

        driver.maximize_window()

        logger.info("Chrome驱动初始化成功")
        return driver

    def _load_cookies(self):
        """加载cookies"""
        if self.cookies_file and os.path.exists(self.cookies_file):
            try:
                with open(self.cookies_file, 'r') as f:
                    cookies = json.load(f)
                    for cookie in cookies:
                        self.driver.add_cookie(cookie)
                logger.info(f"成功加载cookies: {self.cookies_file}")
            except Exception as e:
                logger.error(f"加载cookies失败: {e}")

    def _save_cookies(self):
        """保存cookies"""
        if self.cookies_file:
            try:
                cookies = self.driver.get_cookies()
                with open(self.cookies_file, 'w') as f:
                    json.dump(cookies, f)
                logger.info(f"成功保存cookies: {self.cookies_file}")
            except Exception as e:
                logger.error(f"保存cookies失败: {e}")

    def login_manual(self, wait_time: int = 60):
        """
        手动登录Twitter

        Args:
            wait_time: 等待登录完成的时间（秒）
        """
        logger.info("请在浏览器中手动登录Twitter...")
        self.driver.get("https://twitter.com/login")

        # 等待用户手动登录
        input(f"请在 {wait_time} 秒内完成登录，完成后按Enter键继续...")

        # 保存cookies
        self._save_cookies()
        logger.info("登录完成，cookies已保存")

    def build_search_url(self, username: str, since: str = None, until: str = None) -> str:
        """
        构建Twitter高级搜索URL

        Args:
            username: Twitter用户名（不含@）
            since: 开始日期 (YYYY-MM-DD)
            until: 结束日期 (YYYY-MM-DD)

        Returns:
            搜索URL
        """
        query = f"from:{username}"

        if since:
            query += f" since:{since}"
        if until:
            query += f" until:{until}"

        # URL编码会由selenium自动处理
        url = f"https://twitter.com/search?q={query}&src=typed_query&f=live"
        return url

    def _scroll_page(self, scroll_times: int = 5, scroll_pause: float = 2.0):
        """
        滚动页面以加载更多内容

        Args:
            scroll_times: 滚动次数
            scroll_pause: 每次滚动后的暂停时间（秒）
        """
        for i in range(scroll_times):
            # 滚动到页面底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause)
            logger.info(f"第 {i+1}/{scroll_times} 次滚动")

    def _extract_tweet_data(self, tweet_element) -> Optional[Dict]:
        """
        从推文元素中提取数据

        Args:
            tweet_element: 推文的HTML元素

        Returns:
            包含推文数据的字典
        """
        try:
            tweet_data = {}

            # 提取用户名
            try:
                username_elem = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="User-Name"]')
                tweet_data['username'] = username_elem.text
            except NoSuchElementException:
                tweet_data['username'] = ''

            # 提取推文文本
            try:
                text_elem = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="tweetText"]')
                tweet_data['text'] = text_elem.text
            except NoSuchElementException:
                tweet_data['text'] = ''

            # 提取时间
            try:
                time_elem = tweet_element.find_element(By.CSS_SELECTOR, 'time')
                tweet_data['timestamp'] = time_elem.get_attribute('datetime')
            except NoSuchElementException:
                tweet_data['timestamp'] = ''

            # 提取推文链接
            try:
                link_elem = tweet_element.find_element(By.CSS_SELECTOR, 'a[href*="/status/"]')
                tweet_data['url'] = link_elem.get_attribute('href')
                # 从URL中提取推文ID
                if '/status/' in tweet_data['url']:
                    tweet_data['tweet_id'] = tweet_data['url'].split('/status/')[-1].split('?')[0]
                else:
                    tweet_data['tweet_id'] = ''
            except NoSuchElementException:
                tweet_data['url'] = ''
                tweet_data['tweet_id'] = ''

            # 提取互动数据
            try:
                # 回复数
                reply_elem = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="reply"]')
                tweet_data['replies'] = reply_elem.get_attribute('aria-label') or '0'
            except NoSuchElementException:
                tweet_data['replies'] = '0'

            try:
                # 转推数
                retweet_elem = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="retweet"]')
                tweet_data['retweets'] = retweet_elem.get_attribute('aria-label') or '0'
            except NoSuchElementException:
                tweet_data['retweets'] = '0'

            try:
                # 点赞数
                like_elem = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="like"]')
                tweet_data['likes'] = like_elem.get_attribute('aria-label') or '0'
            except NoSuchElementException:
                tweet_data['likes'] = '0'

            return tweet_data

        except Exception as e:
            logger.error(f"提取推文数据失败: {e}")
            return None

    def crawl_user_tweets(self, username: str, max_scrolls: int = 10,
                         since: str = None, until: str = None) -> List[Dict]:
        """
        爬取指定用户的推文

        Args:
            username: Twitter用户名（不含@）
            max_scrolls: 最大滚动次数
            since: 开始日期 (YYYY-MM-DD)
            until: 结束日期 (YYYY-MM-DD)

        Returns:
            包含所有推文数据的列表
        """
        try:
            # 初始化驱动
            self.driver = self._setup_driver()

            # 先访问Twitter首页
            self.driver.get("https://twitter.com")
            time.sleep(2)

            # 加载cookies
            self._load_cookies()

            # 构建搜索URL
            search_url = self.build_search_url(username, since, until)
            logger.info(f"访问搜索URL: {search_url}")

            self.driver.get(search_url)
            time.sleep(5)

            # 检查是否需要登录
            if "login" in self.driver.current_url:
                logger.warning("需要登录Twitter")
                self.login_manual()
                self.driver.get(search_url)
                time.sleep(5)

            # 滚动并收集推文
            seen_tweet_ids = set()

            for scroll in range(max_scrolls):
                logger.info(f"开始第 {scroll + 1}/{max_scrolls} 轮数据收集")

                # 查找所有推文元素
                tweet_elements = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
                logger.info(f"找到 {len(tweet_elements)} 个推文元素")

                # 提取数据
                for tweet_elem in tweet_elements:
                    tweet_data = self._extract_tweet_data(tweet_elem)

                    if tweet_data and tweet_data.get('tweet_id'):
                        # 去重
                        if tweet_data['tweet_id'] not in seen_tweet_ids:
                            seen_tweet_ids.add(tweet_data['tweet_id'])
                            self.tweets_data.append(tweet_data)
                            logger.info(f"收集推文: {tweet_data['tweet_id']}")

                # 滚动页面
                self._scroll_page(scroll_times=1, scroll_pause=3)

                logger.info(f"当前已收集 {len(self.tweets_data)} 条推文")

            logger.info(f"爬取完成！共收集 {len(self.tweets_data)} 条推文")
            return self.tweets_data

        except Exception as e:
            logger.error(f"爬取过程出错: {e}")
            raise

        finally:
            if self.driver:
                self.driver.quit()

    def save_to_json(self, filename: str = None):
        """保存数据到JSON文件"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tweets_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.tweets_data, f, ensure_ascii=False, indent=2)

        logger.info(f"数据已保存到: {filename}")

    def save_to_csv(self, filename: str = None):
        """保存数据到CSV文件"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tweets_{timestamp}.csv"

        if not self.tweets_data:
            logger.warning("没有数据可保存")
            return

        keys = self.tweets_data[0].keys()

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.tweets_data)

        logger.info(f"数据已保存到: {filename}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='Twitter高级搜索爬虫')
    parser.add_argument('username', help='要爬取的Twitter用户名（不含@）')
    parser.add_argument('--max-scrolls', type=int, default=10,
                       help='最大滚动次数（默认: 10）')
    parser.add_argument('--since', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--until', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--headless', action='store_true',
                       help='使用无头模式')
    parser.add_argument('--cookies', default='twitter_cookies.json',
                       help='cookies文件路径')
    parser.add_argument('--output-json', help='输出JSON文件名')
    parser.add_argument('--output-csv', help='输出CSV文件名')

    args = parser.parse_args()

    # 创建爬虫实例
    crawler = TwitterCrawler(headless=args.headless, cookies_file=args.cookies)

    # 开始爬取
    crawler.crawl_user_tweets(
        username=args.username,
        max_scrolls=args.max_scrolls,
        since=args.since,
        until=args.until
    )

    # 保存数据
    if args.output_json:
        crawler.save_to_json(args.output_json)
    else:
        crawler.save_to_json()

    if args.output_csv:
        crawler.save_to_csv(args.output_csv)
    else:
        crawler.save_to_csv()


if __name__ == '__main__':
    main()

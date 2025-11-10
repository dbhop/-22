#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Twitter爬虫使用示例
"""

from twitter_crawler import TwitterCrawler
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)


def example_basic():
    """基本使用示例"""
    print("=" * 50)
    print("示例 1: 基本使用")
    print("=" * 50)

    # 创建爬虫实例
    crawler = TwitterCrawler(
        headless=False,  # 显示浏览器窗口
        cookies_file='twitter_cookies.json'
    )

    # 爬取推文
    tweets = crawler.crawl_user_tweets(
        username='elonmusk',  # 用户名
        max_scrolls=5  # 滚动5次
    )

    # 保存数据
    crawler.save_to_json('example_tweets.json')
    crawler.save_to_csv('example_tweets.csv')

    # 输出统计信息
    print(f"\n共爬取 {len(tweets)} 条推文")
    if tweets:
        print("\n最新的5条推文:")
        for i, tweet in enumerate(tweets[:5], 1):
            print(f"{i}. {tweet.get('timestamp', 'N/A')}: {tweet.get('text', 'N/A')[:80]}...")


def example_with_date_range():
    """带日期范围的示例"""
    print("\n" + "=" * 50)
    print("示例 2: 爬取特定时间段的推文")
    print("=" * 50)

    crawler = TwitterCrawler(
        headless=True,  # 无头模式
        cookies_file='twitter_cookies.json'
    )

    # 爬取2024年1月的推文
    tweets = crawler.crawl_user_tweets(
        username='elonmusk',
        max_scrolls=10,
        since='2024-01-01',
        until='2024-01-31'
    )

    crawler.save_to_json('tweets_january_2024.json')

    print(f"\n共爬取 {len(tweets)} 条推文")


def example_multiple_users():
    """爬取多个用户的示例"""
    print("\n" + "=" * 50)
    print("示例 3: 爬取多个用户")
    print("=" * 50)

    users = ['elonmusk', 'BillGates', 'tim_cook']

    for username in users:
        print(f"\n正在爬取 @{username} 的推文...")

        crawler = TwitterCrawler(
            headless=True,
            cookies_file='twitter_cookies.json'
        )

        tweets = crawler.crawl_user_tweets(
            username=username,
            max_scrolls=5
        )

        # 为每个用户保存单独的文件
        crawler.save_to_json(f'tweets_{username}.json')

        print(f"@{username}: 共爬取 {len(tweets)} 条推文")


def example_analyze_tweets():
    """分析推文数据的示例"""
    print("\n" + "=" * 50)
    print("示例 4: 爬取并分析推文")
    print("=" * 50)

    crawler = TwitterCrawler(
        headless=True,
        cookies_file='twitter_cookies.json'
    )

    tweets = crawler.crawl_user_tweets(
        username='elonmusk',
        max_scrolls=10
    )

    if tweets:
        # 统计分析
        total_likes = 0
        total_retweets = 0
        total_replies = 0

        for tweet in tweets:
            # 提取数字（简单处理）
            try:
                likes = tweet.get('likes', '0')
                # 处理可能的格式如 "100 Likes"
                if isinstance(likes, str):
                    likes = ''.join(filter(str.isdigit, likes))
                    total_likes += int(likes) if likes else 0
            except:
                pass

        print(f"\n数据统计:")
        print(f"总推文数: {len(tweets)}")
        print(f"总点赞数: {total_likes}")

        # 找出最受欢迎的推文
        print("\n最受欢迎的推文 (前5条):")
        sorted_tweets = sorted(tweets, key=lambda x: x.get('likes', '0'), reverse=True)
        for i, tweet in enumerate(sorted_tweets[:5], 1):
            print(f"{i}. 点赞: {tweet.get('likes', '0')}")
            print(f"   内容: {tweet.get('text', 'N/A')[:80]}...")
            print(f"   链接: {tweet.get('url', 'N/A')}\n")

    crawler.save_to_json('analyzed_tweets.json')


def main():
    """主函数 - 运行所有示例"""
    print("Twitter爬虫使用示例")
    print("=" * 50)

    # 选择要运行的示例
    print("\n请选择要运行的示例:")
    print("1. 基本使用")
    print("2. 爬取特定时间段")
    print("3. 爬取多个用户")
    print("4. 爬取并分析")
    print("5. 运行所有示例")

    choice = input("\n请输入选项 (1-5): ").strip()

    try:
        if choice == '1':
            example_basic()
        elif choice == '2':
            example_with_date_range()
        elif choice == '3':
            example_multiple_users()
        elif choice == '4':
            example_analyze_tweets()
        elif choice == '5':
            example_basic()
            example_with_date_range()
            example_multiple_users()
            example_analyze_tweets()
        else:
            print("无效的选项！")
            return

        print("\n" + "=" * 50)
        print("示例运行完成！")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

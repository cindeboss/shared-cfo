#!/usr/bin/env python3
"""
测试国家税务总局网站结构
"""
import requests
from bs4 import BeautifulSoup
import json

def test_site_structure():
    """测试网站结构"""

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }

    session = requests.Session()
    session.headers.update(headers)

    # 测试几个可能的URL
    urls = [
        'https://fgk.chinatax.gov.cn/',
        'https://fgk.chinatax.gov.cn/zcfgk/c100006/listflfg.html',
        'https://fgk.chinatax.gov.cn/zcfgk/c100006/',
        'https://fgk.chinatax.gov.cn/zcfgk/',
    ]

    for url in urls:
        print(f"\n{'='*60}")
        print(f"测试URL: {url}")
        print('='*60)

        try:
            response = session.get(url, timeout=15)
            print(f"状态码: {response.status_code}")
            print(f"实际URL: {response.url}")

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # 查找所有链接
                links = soup.find_all('a', href=True)
                policy_links = []

                for link in links:
                    href = link.get('href', '')
                    title = link.get_text(strip=True)

                    # 过滤政策相关链接
                    if any(kw in title for kw in ['政策', '公告', '通知', '税']) and href and title:
                        if not href.startswith('http'):
                            from urllib.parse import urljoin
                            href = urljoin(url, href)

                        policy_links.append({
                            'title': title[:100],
                            'href': href
                        })

                print(f"\n找到 {len(policy_links)} 条政策相关链接")
                if policy_links:
                    print("\n前5条:")
                    for i, link in enumerate(policy_links[:5], 1):
                        print(f"{i}. {link['title']}")
                        print(f"   {link['href']}")

                # 保存完整HTML用于分析
                with open(f'site_{url.replace("https://", "").replace("/", "_")}.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"\n已保存HTML到文件")

        except Exception as e:
            print(f"错误: {e}")

if __name__ == '__main__':
    test_site_structure()

from dateutil.relativedelta import relativedelta
import os
import logging
import sys
from datetime import datetime, timedelta
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re
import concurrent.futures
from functools import lru_cache
import hashlib
import pickle
import random

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('../logs/scraper_parallel.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# 共通の定数
COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3'
}
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
SCRAPING_MONTHS = 6
CACHE_DURATION = 6  # キャッシュの有効期間（時間）

class ParallelVenueScraper:
    def __init__(self, max_workers=5, use_cache=True):
        self.logger = logging.getLogger(__name__)
        self.max_workers = max_workers
        self.use_cache = use_cache
        self.cache_dir = '../cache'
        self.session = self.init_session()
        if use_cache:
            os.makedirs(self.cache_dir, exist_ok=True)

    def init_session(self):
        """セッションを初期化"""
        session = requests.Session()
        session.headers.update(COMMON_HEADERS)
        return session

    def scrape_all_venues(self, venues):
        """並列処理で全会場のスクレイピングを実行"""
        all_events = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 各会場のスクレイピングをSubmit
            future_to_url = {executor.submit(self.scrape_venue, url): url 
                           for url in venues}
            
            # 結果の取得
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    events = future.result()
                    all_events.extend(events)
                    self.logger.info(f"Successfully scraped {url}")
                except Exception as e:
                    self.logger.error(f"Error scraping {url}: {str(e)}")
        
        return all_events

    @lru_cache(maxsize=100)
    def get_cached_request(self, url):
        """キャッシュを使用したリクエスト処理"""
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_file = os.path.join(self.cache_dir, f'{cache_key}.pkl')
        
        # キャッシュが有効な場合は使用
        if self.use_cache and os.path.exists(cache_file):
            cache_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - cache_time < timedelta(hours=CACHE_DURATION):
                with open(cache_file, 'rb') as f:
                    self.logger.debug(f"Using cached data for {url}")
                    return pickle.load(f)
        
        # 新しいリクエストを実行
        response = self.make_request(url)
        
        # キャッシュの保存
        if self.use_cache:
            with open(cache_file, 'wb') as f:
                pickle.dump(response, f)
        
        return response

    def make_request(self, url, timeout=REQUEST_TIMEOUT, max_retries=MAX_RETRIES):
        """レート制限に対応したリクエスト実行関数"""
        # レート制限のための遅延
        time.sleep(random.uniform(1, 3))  # 1-3秒のランダムな待機
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=timeout)
                response.encoding = 'utf-8'
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # レート制限
                    wait_time = int(response.headers.get('Retry-After', 60))
                    self.logger.warning(f"Rate limited. Waiting {wait_time} seconds")
                    time.sleep(wait_time)
                    continue
                    
                self.logger.warning(f"Attempt {attempt + 1}/{max_retries}: Status code {response.status_code} for {url}")
                
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed all {max_retries} attempts to fetch {url}: {str(e)}")
                    raise
                self.logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                
            time.sleep(2 ** attempt)
        
        raise requests.RequestException(f"Failed to fetch {url} after {max_retries} attempts")

    def scrape_venue(self, url):
        """会場に応じたスクレイピングを実行"""
        from scraper import scrape_venue  # 既存のスクレイピング関数をインポート
        try:
            events = scrape_venue(url)
            return events
        except Exception as e:
            self.logger.error(f"Error scraping {url}: {str(e)}")
            raise

def save_data(data):
    """スクレイピングしたデータを保存"""
    try:
        if not data:
            logging.warning("No data to save")
            return
        
        # データの重複を除去
        unique_data = []
        seen = set()
        
        for event in data:
            event_key = (event['date'], event['artist'], event['venue'])
            
            if event_key not in seen:
                seen.add(event_key)
                unique_data.append(event)
        
        # ファイル保存
        os.makedirs('../data', exist_ok=True)
        
        # JSONファイルの保存
        with open('../data/events.json', 'w', encoding='utf-8') as f:
            json.dump(unique_data, f, ensure_ascii=False, indent=2)
        
        # CSVファイルの保存
        df = pd.DataFrame(unique_data)
        df.to_csv('../data/events.csv', index=False, encoding='utf-8')
        
        logging.info(f"Saved {len(unique_data)} events (removed {len(data) - len(unique_data)} duplicates)")
        
    except Exception as e:
        logging.error(f"Error saving data: {str(e)}")

def main():
    """メイン実行関数"""
    venues = [
        "https://fireloop.net/schedule_now.shtml",
        "https://para-dice.net/",
        "https://vijon.jp",
        "https://bangboo.jp",
        "https://clubdrop.jp",
        "https://osaka-varon.jp",
        "https://osaka-zeela.jp",
        "https://www.club-quattro.com/umeda",
        "http://rocktown.jp",
        "http://www.knave.co.jp",
        "http://www.namba-hatch.com",
        "http://osaka.muse-live.com",
        "https://livepangea.com"
    ]
    
    # 並列処理用スクレイパーの初期化
    scraper = ParallelVenueScraper(
        max_workers=5,  # 同時実行数
        use_cache=True  # キャッシュの使用
    )
    
    # 並列処理でスクレイピングを実行
    all_events = scraper.scrape_all_venues(venues)
    
    # データの保存
    save_data(all_events)

if __name__ == "__main__":
    main()
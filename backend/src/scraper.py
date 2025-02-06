from dateutil.relativedelta import relativedelta
import os
import logging
import sys
from datetime import datetime
import time  # 追加
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re
sys.path.append(os.path.dirname(__file__))
from utils import create_event

# logsディレクトリが存在しない場合は作成
log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)

# ログファイルのパスを絶対パスで指定
log_file = os.path.join(log_dir, 'scraper.log')

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# 共通のリクエストヘッダー
COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3'
}

REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
SCRAPING_MONTHS = 6

def clean_artist_name(artist_name, debug=False):
    """アーティスト名から余分な情報を除去する共通関数"""
    if not artist_name:
        return ""
    
    # デバッグログの制御
    logger = logging.getLogger(__name__)
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    if debug:
        logger.debug(f"Cleaning artist name: {artist_name}")
    
    name = artist_name.strip()
    
    patterns = [
        r'\([^)]+\)',          # (文字列)
        r'（[^）]+）',         # （文字列）
        r'【[^】]+】',         # 【文字列】
        r'\[[^\]]+\]',         # [文字列]
        r'［[^］]+］',         # ［文字列］
        r'feat\.[^　]*',       # feat.以降
        r'from\s+[^　]*',      # fromの後の所属グループ名
    ]
    
    # 各パターンを順番に適用
    for pattern in patterns:
        before = name
        name = re.sub(pattern, '', name)
        if debug and before != name:
            logger.debug(f"Removed {pattern}: {before} -> {name}")
    
    result = name.strip()
    
    if debug:
        logger.debug(f"Final result: {result}")
        
    return result

def parse_date(date_text, format_type='default'):
    """日付文字列を解析して標準形式（YYYY/MM/DD）に変換する共通関数
    
    format_type:
        'default': 標準的な日付形式（2025/02/01）
        'dot': ドット区切り（2.1や2025.2.1）
        'slash_short': スラッシュ区切り（2/1）
        'mixed': 混合フォーマット
    """
    try:
        current_date = datetime.now()
        
        if format_type == 'dot':
            # 2.1 や 2025.2.1 形式
            parts = date_text.split('.')
            if len(parts) == 2:
                month, day = map(int, parts)
                year = current_date.year
            elif len(parts) == 3:
                year, month, day = map(int, parts)
            else:
                raise ValueError(f"Invalid dot format: {date_text}")
                
        elif format_type == 'slash_short':
            # 2/1 形式
            month, day = map(int, date_text.split('/'))
            year = current_date.year
            
        elif format_type == 'mixed':
            # 正規表現で数字を抽出
            numbers = re.findall(r'\d+', date_text)
            if len(numbers) < 2:
                raise ValueError(f"Not enough numbers in date: {date_text}")
            
            if len(numbers) == 2:
                month, day = map(int, numbers)
                year = current_date.year
            else:
                year = int(numbers[0])
                month = int(numbers[1])
                day = int(numbers[2])
                
        else:  # default
            year, month, day = map(int, date_text.split('/'))
        
        # 年の調整（月が現在より小さい場合は来年）
        if len(str(year)) == 2:
            year += 2000
        
        if month < current_date.month and year == current_date.year:
            year += 1
            
        # 日付の妥当性チェック
        datetime(year, month, day)
        
        return f"{year}/{month:02d}/{day:02d}"
        
    except Exception as e:
        logging.debug(f"Date parsing failed for {date_text}: {str(e)}")
        raise ValueError(f"Invalid date format: {date_text}")


def get_venue_name(base_url):
    """URLから会場名を取得"""
    venue_map = {
        'vijon.jp': '北堀江club vijon',
        'bangboo.jp': '梅田BANGBOO',
        'clubdrop.jp': 'アメリカ村DROP',
        'osaka-varon.jp': 'VARON',
        'osaka-zeela.jp': 'Zeela'
    }
    
    for domain, name in venue_map.items():
        if domain in base_url:
            return name
    return "Unknown Venue"

def scrape_fireloop(url):
    """寺田町Fireloopのスクレイピング"""
    logger = logging.getLogger(__name__)
    logger.info("=== Fireloop Scraping Start ===")
    events = []

    try:
        session = init_session()
        response = make_request(session, url)
        soup = BeautifulSoup(response.text, 'html.parser')

        schedule_divs = soup.find_all('div', class_='pager')
        logger.info(f"Found {len(schedule_divs)} schedule days")

        for schedule_div in schedule_divs:
            try:
                event_div = schedule_div.find('div', class_='half-page left')
                if not event_div:
                    continue

                # 日付の取得と解析
                date_id = event_div.get('id', '')
                date_elem = event_div.find('h2', class_='datef')
                weekday_elem = date_elem.find('div', class_='weekday') if date_elem else None
                
                if not (date_id and date_elem):
                    continue

                try:
                    month = date_id[:2]
                    day = date_id[2:]
                    date = parse_date(f"{month}/{day}", format_type='slash_short')
                except ValueError as e:
                    logger.debug(f"Date parsing failed: {str(e)}")
                    continue

                weekday_map = {'MON': '月', 'TUE': '火', 'WED': '水', 
                            'THU': '木', 'FRI': '金', 'SAT': '土', 'SUN': '日'}
                day_en = weekday_elem.text.strip() if weekday_elem else ''
                day_jp = weekday_map.get(day_en, '')

                # イベント情報の取得
                title_elem = event_div.find('div', class_='title')
                title = title_elem.text.strip() if title_elem else ''

                cast_elem = event_div.find('div', class_='cast')
                if not cast_elem:
                    continue

                artists = [clean_artist_name(artist.strip(), debug=False) 
                          for artist in cast_elem.stripped_strings]
                artists = [a for a in artists if a]  # 空の要素を除去

                # 公演区分の取得
                date_text = date_elem.text.strip() if date_elem else ''
                note = '昼公演' if '昼公演' in date_text else ''
                if not note and '夜公演' in date_text:
                    note = '夜公演'

                # イベントの作成
                for artist in artists:
                    event = create_event(
                        date=date,
                        day_jp=day_jp,
                        artist=artist,
                        title=title,
                        url=f"{url}#{date_id}",
                        venue='寺田町Fireloop',
                        note=''
                    )
                    events.append(event)
                    logger.debug(f"Created event: {event}")

            except Exception as e:
                logger.error(f"Error parsing schedule div: {str(e)}", exc_info=True)
                continue

        logger.info(f"Total events found: {len(events)}")
        return events

    except Exception as e:
        logger.error(f"Error scraping Fireloop: {str(e)}", exc_info=True)
        return []

def scrape_paradice(url):
    """扇町para-diceのスクレイピング"""
    logger = logging.getLogger(__name__)
    logger.info("=== Para-dice Scraping Start ===")
    events = []

    try:
        session = init_session()
        response = make_request(session, url)
        soup = BeautifulSoup(response.text, 'html.parser')

        schedule_rows = soup.find_all('tr')
        logger.info(f"Found {len(schedule_rows)} schedule rows")

        # 除外するパターン
        exclude_patterns = [
            r'^■',          # ■から始まる行
            r'前売',
            r'当日',
            r'OPEN',
            r'START',
            r'\d+円',       # 料金表示
            r'^\d+:\d+$',   # 時間のみの表示
            r'問い合わせ',
            r'チケット',
        ]
        exclude_regex = re.compile('|'.join(exclude_patterns))

        for row in schedule_rows:
            try:
                date_th = row.find('th')
                if not date_th or not date_th.find_all('p'):
                    continue

                # 日付と曜日の取得
                date_text = date_th.find_all('p')[0].text.strip()
                weekday_text = date_th.find_all('p')[1].text.strip()

                try:
                    # 日付の解析
                    date = parse_date(date_text, format_type='slash_short')
                    day_jp = weekday_text.strip('()')
                except ValueError as e:
                    logger.debug(f"Date parsing failed: {str(e)}")
                    continue

                event_td = row.find('td')
                if not event_td:
                    continue

                # タイトルの取得
                title_elem = event_td.find('strong')
                title = title_elem.text.strip() if title_elem else ""

                # アーティスト情報の取得と処理
                artist_elements = event_td.find_all('p')
                artists_found = False
                
                for elem in artist_elements:
                    text = elem.text.strip()
                    
                    if exclude_regex.search(text):
                        continue

                    # 各パターンでアーティスト名を抽出
                    patterns = [
                        (r'\d{2}:\d{2} 〜 \d{2}:\d{2} (.+)', 1),  # 時間パターン
                        (r'出演：(.+)', 1),                        # 出演者パターン
                    ]

                    artist_names = []
                    for pattern, group in patterns:
                        match = re.match(pattern, text)
                        if match:
                            artist_names.append(match.group(group))
                            break
                    
                    if '/' in text and not artist_names:
                        artist_names.extend(text.split('/'))
                    elif not artist_names and not exclude_regex.search(text):
                        artist_names.append(text)

                    # アーティスト名の処理とイベント作成
                    for artist_name in artist_names:
                        artist = clean_artist_name(artist_name.strip(), debug=False)
                        if artist:
                            event = create_event(
                                date=date,
                                day_jp=day_jp,
                                artist=artist,
                                title=title,
                                url=url,
                                venue='扇町para-dice',
                                note=''
                            )
                            events.append(event)
                            artists_found = True
                            logger.debug(f"Created event: {event}")

                if not artists_found:
                    logger.debug(f"No artists found in row with date {date}")

            except Exception as e:
                logger.error(f"Error parsing schedule row: {str(e)}", exc_info=True)
                continue

        logger.info(f"Total events found: {len(events)}")
        return events

    except Exception as e:
        logger.error(f"Error scraping Para-dice: {str(e)}", exc_info=True)
        return []


def parse_date(date_text, format_type='default'):
    """日付文字列を解析して標準形式（YYYY/MM/DD）に変換する共通関数
    
    format_type:
        'default': 標準的な日付形式（2025/02/01）
        'dot': ドット区切り（2.1や2025.2.1）
        'slash_short': スラッシュ区切り（2/1）
        'mixed': 混合フォーマット
    """
    try:
        current_date = datetime.now()
        
        if format_type == 'dot':
            # 2.1 や 2025.2.1 形式
            parts = date_text.split('.')
            if len(parts) == 2:
                month, day = map(int, parts)
                year = current_date.year
            elif len(parts) == 3:
                year, month, day = map(int, parts)
            else:
                raise ValueError(f"Invalid dot format: {date_text}")
                
        elif format_type == 'slash_short':
            # 2/1 形式
            month, day = map(int, date_text.split('/'))
            year = current_date.year
            
        elif format_type == 'mixed':
            # 正規表現で数字を抽出
            numbers = re.findall(r'\d+', date_text)
            if len(numbers) < 2:
                raise ValueError(f"Not enough numbers in date: {date_text}")
            
            if len(numbers) == 2:
                month, day = map(int, numbers)
                year = current_date.year
            else:
                year = int(numbers[0])
                month = int(numbers[1])
                day = int(numbers[2])
                
        else:  # default
            year, month, day = map(int, date_text.split('/'))
        
        # 年の調整（月が現在より小さい場合は来年）
        if len(str(year)) == 2:
            year += 2000
        
        if month < current_date.month and year == current_date.year:
            year += 1
            
        # 日付の妥当性チェック
        datetime(year, month, day)
        
        return f"{year}/{month:02d}/{day:02d}"
        
    except Exception as e:
        logging.debug(f"Date parsing failed for {date_text}: {str(e)}")
        raise ValueError(f"Invalid date format: {date_text}")


def make_request(session, url, timeout=REQUEST_TIMEOUT, max_retries=MAX_RETRIES):
    """HTTPリクエストを実行する共通関数（リトライ機能付き）"""
    logger = logging.getLogger(__name__)
    
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=timeout)
            response.encoding = 'utf-8'
            
            if response.status_code == 200:
                return response
                
            logger.warning(f"Attempt {attempt + 1}/{max_retries}: Status code {response.status_code} for {url}")
            
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed all {max_retries} attempts to fetch {url}: {str(e)}")
                raise
            logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
            
        # 再試行前に少し待機（1秒、2秒、4秒...）
        time.sleep(2 ** attempt)
    
    raise requests.RequestException(f"Failed to fetch {url} after {max_retries} attempts")

def init_session():
    """セッションを初期化する共通関数"""
    session = requests.Session()
    session.headers.update(COMMON_HEADERS)
    return session

    
def get_next_n_months(n: int = SCRAPING_MONTHS):
    """今月から指定月数分の年月を生成する共通関数"""
    current = datetime.now()
    months = []
    for i in range(n):
        next_date = current.replace(day=1) + relativedelta(months=i)
        months.append((next_date.year, next_date.month))
    return months


def get_weekday_jp(date_str):
    """日付文字列から日本語の曜日を取得する共通関数"""
    date = datetime.strptime(date_str, '%Y/%m/%d')
    weekday_map = {
        0: '月', 1: '火', 2: '水', 3: '木',
        4: '金', 5: '土', 6: '日'
    }
    return weekday_map[date.weekday()]


def scrape_vijon_system(base_url):
    """vijon系列のライブハウスのスクレイピング"""
    logger = logging.getLogger(__name__)
    venue_name = get_venue_name(base_url)
    logger.info(f"=== {venue_name} ({base_url}) Scraping Start ===")
    events = []

    try:
        session = init_session()
        
        # 6ヶ月分のスケジュールを取得
        for year, month in get_next_n_months():
            calendar_url = f"{base_url}/schedule/calendar/{year}/{month:02d}/"
            logger.info(f"Scraping calendar: {calendar_url}")
            
            try:
                response = make_request(session, calendar_url)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # イベントリンクを取得
                event_links = soup.select('a[href*="/schedule/detail/"]')
                logger.info(f"Found {len(event_links)} events in {year}/{month:02d}")
                
                for link in event_links:
                    try:
                        detail_url = link.get('href')
                        if not detail_url.startswith('http'):
                            domain = base_url.split('://')[1]
                            detail_url = f"https://{domain}{detail_url}"
                            
                        detail_events = scrape_vijon_detail(session, detail_url, venue_name)
                        events.extend(detail_events)
                        
                    except Exception as e:
                        logger.error(f"Error scraping detail page {detail_url}: {str(e)}", exc_info=True)
                        continue
                        
            except Exception as e:
                logger.error(f"Error scraping calendar page {calendar_url}: {str(e)}", exc_info=True)
                continue
                
        logger.info(f"Total events found: {len(events)}")
        return events
        
    except Exception as e:
        logger.error(f"Error scraping {venue_name}: {str(e)}", exc_info=True)
        return []

def scrape_vijon_detail(session, detail_url, venue_name):
    """vijon系列の詳細ページから情報を取得"""
    logger = logging.getLogger(__name__)
    events = []
    
    try:
        response = make_request(session, detail_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 日付情報の取得
        date_elem = soup.select_one('p.day')
        if not date_elem:
            logger.debug(f"No date information found at {detail_url}")
            return events

        date_text = date_elem.text.strip()
        try:
            # 日付とフォーマットの解析
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{2})', date_text)
            weekday_match = re.search(r'\((.*?)\)', date_text)
            
            if not date_match:
                logger.debug(f"Invalid date format: {date_text}")
                return events

            date = parse_date(f"{date_match.group(1)}/{date_match.group(2)}/{date_match.group(3)}")
            
            # 曜日の変換
            weekday_map = {
                'Sun': '日', 'Mon': '月', 'Tue': '火', 
                'Wed': '水', 'Thu': '木', 'Fri': '金', 'Sat': '土'
            }
            day_jp = weekday_map.get(weekday_match.group(1), '') if weekday_match else ''
            
            # タイトルとアーティスト情報の取得
            title_elem = soup.select_one('div.scheduleCnt h1')
            title = title_elem.text.strip() if title_elem else ''
            
            artists_elem = soup.select_one('span.artist')
            if not artists_elem:
                logger.debug(f"No artist information found at {detail_url}")
                return events

            # アーティスト名の処理
            artists = [clean_artist_name(artist.strip(), debug=False) 
                      for artist in artists_elem.text.split('/')]
            artists = [artist for artist in artists if artist]  # 空の要素を除去
            
            # イベントの作成
            for artist in artists:
                event = create_event(
                    date=date,
                    day_jp=day_jp,
                    artist=artist,
                    venue=venue_name,
                    title=title,
                    url=detail_url
                )
                events.append(event)
                logger.debug(f"Created event: {event}")

        except ValueError as e:
            logger.debug(f"Date parsing error at {detail_url}: {str(e)}")
            return events
    
    except Exception as e:
        logger.error(f"Error processing detail page {detail_url}: {str(e)}", exc_info=True)
        return events
        
    return events

def scrape_vijon_detail(session, detail_url, venue_name):
    """vijon系列の詳細ページから情報を取得"""
    logger = logging.getLogger(__name__)
    events = []
    
    try:
        response = make_request(session, detail_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 日付情報の取得と解析
        date_elem = soup.select_one('p.day')
        if not date_elem:
            logger.debug(f"No date information found at {detail_url}")
            return events

        date_text = date_elem.text.strip()
        date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{2})', date_text)
        weekday_match = re.search(r'\((.*?)\)', date_text)
        
        if not date_match:
            logger.debug(f"Invalid date format: {date_text}")
            return events

        # 日付と曜日の解析
        date = f"{date_match.group(1)}/{date_match.group(2).zfill(2)}/{date_match.group(3)}"
        weekday_map = {
            'Sun': '日', 'Mon': '月', 'Tue': '火', 
            'Wed': '水', 'Thu': '木', 'Fri': '金', 'Sat': '土'
        }
        day_jp = weekday_map.get(weekday_match.group(1), '') if weekday_match else ''
        
        # タイトルとアーティスト情報の取得
        title_elem = soup.select_one('div.scheduleCnt h1')
        title = title_elem.text.strip() if title_elem else ''
        
        artists_elem = soup.select_one('span.artist')
        if not artists_elem:
            logger.debug(f"No artist information found at {detail_url}")
            return events

        # アーティスト名の処理
        for artist_name in artists_elem.text.split('/'):
            artist = clean_artist_name(artist_name.strip(), debug=False)
            if artist:
                event = create_event(
                    date=date,
                    day_jp=day_jp,
                    artist=artist,
                    venue=venue_name,
                    title=title,
                    url=detail_url,
                    note=''
                )
                events.append(event)
                logger.debug(f"Created event: {event}")
    
    except Exception as e:
        logger.error(f"Error processing detail page {detail_url}: {str(e)}", exc_info=True)
        
    return events
    

def scrape_bigcat(base_url):
    """BIGCATのスケジュールをスクレイピング"""
    logger = logging.getLogger(__name__)
    logger.info("=== BIGCAT Scraping Start ===")
    events = []

    try:
        session = init_session()
        current = datetime.now()
        
        # 現在の月と次の月のスケジュールを取得
        for month_offset in range(2):  # BIGCATは2ヶ月分のみ
            target_date = current.replace(day=1) + relativedelta(months=month_offset)
            schedule_url = f"{base_url}/{target_date.year}/{target_date.month}"
            logger.info(f"Scraping schedule: {schedule_url}")

            try:
                response = make_request(session, schedule_url)
                soup = BeautifulSoup(response.text, 'html.parser')

                # イベントの取得
                schedule_items = soup.select('div.archive_block')
                logger.info(f"Found {len(schedule_items)} events")
                
                for item in schedule_items:
                    try:
                        # 日付の取得
                        date_elem = item.select_one('.date_txt')
                        if not date_elem:
                            continue

                        # 日付の解析
                        try:
                            date = parse_date(date_elem.text.strip(), format_type='dot')
                        except ValueError as e:
                            logger.debug(f"Date parsing failed: {str(e)}")
                            continue
                        
                        # 曜日の取得
                        week_elem = item.select_one('.week')
                        weekday_map = {
                            'MON': '月', 'TUE': '火', 'WED': '水',
                            'THU': '木', 'FRI': '金', 'SAT': '土', 'SUN': '日'
                        }
                        day_jp = weekday_map.get(week_elem.text.strip() if week_elem else '', '')

                        # タイトルの取得
                        title_elem = item.select_one('.ttl')
                        title = title_elem.text.strip() if title_elem else ""

                        # アーティスト情報の取得
                        artists = []
                        live_info = item.select_one('.detail_live dd')
                        if live_info:
                            # メインアーティスト（リンクテキスト）
                            artist_links = live_info.find_all('a')
                            for link in artist_links:
                                artist = clean_artist_name(link.text.strip(), debug=False)
                                if artist:
                                    artists.append(artist)

                            # 対バン情報の処理
                            info_text = live_info.get_text()
                            if '対バン：' in info_text:
                                taiband_text = info_text.split('対バン：')[1].split('\n')[0]
                                for band in taiband_text.split(','):
                                    artist = clean_artist_name(band.strip(), debug=False)
                                    if artist:
                                        artists.append(artist)

                        # イベントの作成
                        for artist in artists:
                            event = create_event(
                                date=date,
                                day_jp=day_jp,
                                artist=artist,
                                title=title,
                                url=schedule_url,
                                venue='BIGCAT',
                                note=''
                            )
                            events.append(event)
                            logger.debug(f"Created event: {event}")

                    except Exception as e:
                        logger.error(f"Error parsing event item: {str(e)}", exc_info=True)
                        continue

            except Exception as e:
                logger.error(f"Error scraping month page {schedule_url}: {str(e)}", exc_info=True)
                continue

        logger.info(f"Total events found: {len(events)}")
        return events

    except Exception as e:
        logger.error(f"Error scraping BIGCAT: {str(e)}", exc_info=True)
        return []
    


def scrape_quattro(base_url):
    """梅田QUATTROのスケジュールをスクレイピング"""
    logger = logging.getLogger(__name__)
    logger.info("=== QUATTRO Scraping Start ===")
    events = []
    
    try:
        session = init_session()
        
        # 6ヶ月分のスケジュールを取得
        for year, month in get_next_n_months():
            schedule_url = f"{base_url}/schedule/?ym={year}{month:02d}"
            logger.info(f"Scraping schedule: {schedule_url}")

            try:
                response = make_request(session, schedule_url)
                soup = BeautifulSoup(response.text, 'html.parser')

                # schedule-boxクラスを持つdivを全て取得
                schedule_items = soup.select('div.schedule-box')
                logger.info(f"Found {len(schedule_items)} schedule items")
                
                for item_idx, item in enumerate(schedule_items, 1):
                    try:
                        # 日付の取得
                        date_div = item.select_one('.event-date')
                        if not date_div:
                            continue
                            
                        date_text = date_div.select_one('.date').text.strip()
                        
                        # イベント日付の取得（クラス名から）
                        date_class = date_div.get('class', [])
                        date_info = next((c for c in date_class if c.startswith('date')), '')
                        
                        try:
                            if date_info:
                                full_date_match = re.search(r'date(\d{4})-(\d{2})-(\d{2})', date_info)
                                if full_date_match:
                                    year = int(full_date_match.group(1))
                                    month = int(full_date_match.group(2))
                                    day = int(date_text)
                                    date = f"{year}/{month:02d}/{day:02d}"
                                else:
                                    continue
                            else:
                                continue
                        except ValueError as e:
                            logger.debug(f"Date parsing failed: {str(e)}")
                            continue
                        
                        # イベント情報の取得
                        title_elem = item.select_one('.event-ttl')
                        if not title_elem:
                            continue

                        # アーティスト情報の解析
                        artists = []
                        artist_lines = title_elem.text.strip().split('\n')
                        
                        for line in artist_lines:
                            # 不要な文字列を削除
                            line = re.sub(r'＜NEW＞|O\.A\s+', '', line)
                            
                            # スラッシュで区切られたアーティスト
                            for artist_name in line.split('/'):
                                artist = clean_artist_name(artist_name.strip(), debug=False)
                                if artist:
                                    artists.append(artist)

                        # イベントの作成
                        for artist in artists:
                            event = create_event(
                                date=date,
                                day_jp=get_weekday_jp(date),
                                artist=artist,
                                title=title_elem.text.strip(),
                                url=f"{base_url}{item.select_one('a')['href'][1:]}",
                                venue='梅田QUATTRO',
                                note=''
                            )
                            events.append(event)
                            logger.debug(f"Created event: {event}")

                    except Exception as e:
                        logger.error(f"Error parsing item {item_idx}: {str(e)}", exc_info=True)
                        continue

            except Exception as e:
                logger.error(f"Error scraping month page {schedule_url}: {str(e)}", exc_info=True)
                continue

        logger.info(f"Total events found: {len(events)}")
        return events

    except Exception as e:
        logger.error(f"Error scraping QUATTRO: {str(e)}", exc_info=True)
        return []
    


def scrape_rocktown(base_url):
    """あべのROCKTOWNのスケジュールをスクレイピング"""
    logger = logging.getLogger(__name__)
    logger.info("=== ROCKTOWN Scraping Start ===")
    events = []

    try:
        session = init_session()
        
        # 6ヶ月分のスケジュールを取得
        for year, month in get_next_n_months():
            # URLの生成（当月はindex.html、それ以外は年月.html）
            current = datetime.now()
            if year == current.year and month == current.month:
                schedule_url = f"{base_url}/schedule/index.html"
            else:
                schedule_url = f"{base_url}/schedule/{year}{month:02d}.html"

            logger.info(f"Scraping schedule: {schedule_url}")

            try:
                response = make_request(session, schedule_url)
                soup = BeautifulSoup(response.text, 'html.parser')

                # イベントテーブルの取得
                schedule_tables = soup.select('table.date')
                logger.info(f"Found {len(schedule_tables)} schedule tables")
                
                for table_idx, table in enumerate(schedule_tables, 1):
                    try:
                        # 日付の取得（画像ファイル名から）
                        day_img = table.select_one('th img[src*="images"]')
                        if not day_img:
                            continue
                            
                        day_match = re.search(r'(\d+)\.gif$', day_img['src'])
                        if not day_match:
                            continue
                            
                        try:
                            day = int(day_match.group(1))
                            date = f"{year}/{month:02d}/{day:02d}"
                        except ValueError as e:
                            logger.debug(f"Date parsing failed: {str(e)}")
                            continue

                        # タイトル情報の取得
                        title_cell = table.select_one('td.rocktown.title')
                        title = title_cell.text.strip() if title_cell else ""

                        # アーティスト情報の取得
                        artist_cell = table.select_one('tr:nth-child(2) td[colspan="3"]')
                        if not artist_cell:
                            continue

                        # アーティスト名の処理
                        artists = []
                        artist_text = artist_cell.text.strip()
                        
                        # 改行とスラッシュで分割
                        for line in artist_text.split('\n'):
                            for artist_name in line.split('/'):
                                artist = clean_artist_name(artist_name.strip(), debug=False)
                                if artist:
                                    artists.append(artist)

                        # イベントの作成
                        for artist in artists:
                            event = create_event(
                                date=date,
                                day_jp=get_weekday_jp(date),
                                artist=artist,
                                title=title,
                                url=schedule_url,
                                venue='あべのROCKTOWN',
                                note=''
                            )
                            events.append(event)
                            logger.debug(f"Created event: {event}")

                    except Exception as e:
                        logger.error(f"Error parsing table {table_idx}: {str(e)}", exc_info=True)
                        continue

            except Exception as e:
                logger.error(f"Error scraping month page {schedule_url}: {str(e)}", exc_info=True)
                continue

        logger.info(f"Total events found: {len(events)}")
        return events

    except Exception as e:
        logger.error(f"Error scraping ROCKTOWN: {str(e)}", exc_info=True)
        return []


def scrape_knave(base_url):
    """knaveのスケジュールをスクレイピング"""
    logger = logging.getLogger(__name__)
    logger.info("=== knave Scraping Start ===")
    events = []
    
    try:
        session = init_session()
        
        # 6ヶ月分のスケジュールを取得
        for year, month in get_next_n_months():
            schedule_url = f"{base_url}/schedule/s_{year}_{month:02d}.html"
            logger.info(f"Scraping schedule: {schedule_url}")

            try:
                response = make_request(session, schedule_url)
                soup = BeautifulSoup(response.text, 'html.parser')

                # イベント情報の取得
                event_divs = soup.select('div.event-details')
                logger.info(f"Found {len(event_divs)} event details")
                
                for div_idx, event_div in enumerate(event_divs, 1):
                    try:
                        # 日付の取得
                        date_elem = event_div.find_previous('h3', class_='f-22')
                        if not date_elem:
                            continue

                        # 日付のパース (例: "25.2.8" → 2025/02/08)
                        date_text = date_elem.text.strip()
                        try:
                            # 日付解析の共通関数を使用
                            date = parse_date(date_text, format_type='mixed')
                        except ValueError as e:
                            logger.debug(f"Date parsing failed: {str(e)}")
                            continue

                        # イベント詳細の取得
                        event_left = event_div.select_one('.event-details-left')
                        if not event_left:
                            continue

                        # タイトルと出演者情報の取得
                        event_text = event_left.select_one('p.f-12')
                        if not event_text:
                            continue

                        # テキストの分割処理
                        lines = [line.strip() for line in event_text.text.split('\n') if line.strip()]
                        title = lines[0] if lines else ""

                        # アーティスト情報の抽出
                        artists = []
                        artist_lines = lines[1:] if len(lines) > 1 else []
                        
                        for line in artist_lines:
                            # 複数の区切り文字でアーティストを分割
                            if '/' in line:
                                parts = line.split('/')
                            elif ',' in line:
                                parts = line.split(',')
                            else:
                                parts = [line]
                                
                            for part in parts:
                                artist = clean_artist_name(part.strip(), debug=False)
                                if artist:
                                    artists.append(artist)

                        # イベントの作成
                        for artist in artists:
                            event = create_event(
                                date=date,
                                day_jp=get_weekday_jp(date),
                                artist=artist,
                                title=title,
                                url=schedule_url,
                                venue='knave',
                                note=''
                            )
                            events.append(event)
                            logger.debug(f"Created event: {event}")

                    except Exception as e:
                        logger.error(f"Error parsing event div {div_idx}: {str(e)}", exc_info=True)
                        continue

            except Exception as e:
                logger.error(f"Error scraping month page {schedule_url}: {str(e)}", exc_info=True)
                continue

        logger.info(f"Total events found: {len(events)}")
        return events

    except Exception as e:
        logger.error(f"Error scraping knave: {str(e)}", exc_info=True)
        return []



def scrape_hatch(base_url):
    """なんばHatchのスケジュールをスクレイピング"""
    logger = logging.getLogger(__name__)
    logger.info("=== Hatch Scraping Start ===")
    events = []

    try:
        session = init_session()

        # 6ヶ月分のスケジュールを取得
        for month_offset in range(SCRAPING_MONTHS):
            schedule_url = f"{base_url}/schedule.php?add={month_offset}"
            logger.info(f"Scraping schedule: {schedule_url}")

            try:
                response = make_request(session, schedule_url)
                soup = BeautifulSoup(response.text, 'html.parser')

                # スケジュールテーブルの取得
                schedule_table = soup.find('table', class_='scheduleInfo')
                if not schedule_table:
                    logger.warning(f"No schedule table found at {schedule_url}")
                    continue

                schedule_rows = schedule_table.find_all('tr')
                logger.info(f"Found {len(schedule_rows)} schedule rows")
                
                for row_idx, row in enumerate(schedule_rows, 1):
                    try:
                        # 日付情報の取得
                        date_th = row.find('th')
                        if not date_th:
                            continue

                        date_text = date_th.text.strip().split('\n')[0]
                        try:
                            # 日付解析の共通関数を使用
                            date = parse_date(date_text, format_type='slash_short')
                        except ValueError as e:
                            logger.debug(f"Date parsing failed: {str(e)}")
                            continue

                        # イベント情報の取得
                        event_td = row.find('td', class_='bgBlack')
                        if not event_td:
                            continue

                        # アーティストとタイトルの取得
                        artist_div = event_td.find('div', class_='eventArtist')
                        title_div = event_td.find('div', class_='eventTitle')
                        
                        if not artist_div:
                            continue

                        title = title_div.text.strip() if title_div else ""
                        
                        # アーティストの処理
                        artists = []
                        artist_text = artist_div.text.strip()
                        
                        # ゲストアーティストの取得
                        guest_artists = []
                        if 'GUEST' in title:
                            guest_match = re.search(r'GUEST\s*(?:ACT)?[：:]\s*([^<\n]+)', title)
                            if guest_match:
                                guest_text = guest_match.group(1).strip()
                                guest_artists = [clean_artist_name(g.strip(), debug=False) 
                                               for g in re.split(r'[/、]', guest_text)]

                        # メインアーティストの処理
                        for separator in [' / ', '/', '、', ' ']:
                            if separator in artist_text:
                                main_artists = [clean_artist_name(a.strip(), debug=False) 
                                              for a in artist_text.split(separator)]
                                artists.extend(a for a in main_artists if a)
                                break
                        
                        if not artists:
                            artist = clean_artist_name(artist_text, debug=False)
                            if artist:
                                artists.append(artist)

                        # ゲストアーティストを追加
                        artists.extend(a for a in guest_artists if a)

                        # イベントの作成
                        for artist in artists:
                            if artist and len(artist) > 1:  # 空または1文字の名前は除外
                                event = create_event(
                                    date=date,
                                    day_jp=get_weekday_jp(date),
                                    artist=artist,
                                    title=title,
                                    url=schedule_url,
                                    venue='なんばHatch',
                                    note=''
                                )
                                events.append(event)
                                logger.debug(f"Created event: {event}")

                    except Exception as e:
                        logger.error(f"Error parsing row {row_idx}: {str(e)}", exc_info=True)
                        continue

            except Exception as e:
                logger.error(f"Error scraping month page {schedule_url}: {str(e)}", exc_info=True)
                continue

        logger.info(f"Total events found: {len(events)}")
        return events

    except Exception as e:
        logger.error(f"Error scraping Hatch: {str(e)}", exc_info=True)
        return []



def scrape_muse(base_url):
    """心斎橋MUSEのスケジュールをスクレイピング"""
    logger = logging.getLogger(__name__)
    logger.info("=== MUSE Scraping Start ===")
    events = []

    try:
        session = init_session()
        
        # 6ヶ月分のスケジュールを取得
        for month_offset in range(SCRAPING_MONTHS):
            target_date = datetime.now() + relativedelta(months=month_offset)
            schedule_url = f"{base_url}/schedule/?y={target_date.year}&m={target_date.month}"
            logger.info(f"Scraping schedule: {schedule_url}")

            try:
                response = make_request(session, schedule_url)
                soup = BeautifulSoup(response.text, 'html.parser')

                schedule_items = soup.find_all('article', class_='media schedule')
                logger.info(f"Found {len(schedule_items)} schedule items")
                
                for item_idx, item in enumerate(schedule_items, 1):
                    try:
                        logger.debug(f"Processing item {item_idx}")

                        date_div = item.find('div', class_='event_date')
                        if not date_div:
                            logger.debug("No event_date div found")
                            continue

                        # 日付文字列を取得
                        date_text = date_div.get_text(strip=True, separator=' ')
                        logger.debug(f"Raw date text: {date_text}")

                        # 日付形式の変換（dot形式）
                        try:
                            date = parse_date(date_text, format_type='dot')
                            logger.debug(f"Parsed date: {date}")
                        except ValueError as e:
                            logger.debug(f"Date parsing failed: {str(e)}")
                            continue

                        # タイトルの取得
                        title_elem = item.find('h3', class_='media-heading')
                        title = title_elem.text.strip() if title_elem else ""
                        print(f"Found title: {title}")

                        # アーティスト情報の取得
                        content_div = item.find('div', class_='schedule_content')
                        if content_div and content_div.find('p'):
                            artist_text = content_div.find('p').text.strip()
                            print(f"Found artist text: {artist_text}")
                            
                            artists = []
                            # スラッシュ、カンマ、スペースで分割
                            for separator in ['/', '、', ' ']:
                                if separator in artist_text:
                                    parts = [part.strip() for part in artist_text.split(separator)]
                                    artists = [clean_artist_name(part) for part in parts if part]
                                    print(f"Split artists by '{separator}': {artists}")
                                    break
                            
                            if not artists:  # 区切り文字がない場合
                                artists = [clean_artist_name(artist_text)]
                                print(f"Single artist: {artists}")
                        else:
                            print("No artist information found")
                            continue

                        # イベントの作成
                        events_created = 0
                        for artist in artists:
                            if artist and len(artist) > 1:  # 空または1文字の名前は除外
                                event = {
                                    'date': date,
                                    'day': get_weekday_jp(date),
                                    'note': '',
                                    'artist': artist,
                                    'venue': '心斎橋MUSE',
                                    'title': title,
                                    'url': schedule_url
                                }
                                events.append(event)
                                events_created += 1
                                print(f"Created event: {event}")
                        
                        print(f"Created {events_created} events from this item")

                    except Exception as e:
                        print(f"Error parsing item {item_idx}: {str(e)}")
                        import traceback
                        print(traceback.format_exc())
                        continue

            except Exception as e:
                print(f"Error scraping month page {schedule_url}: {str(e)}")
                continue

        print(f"\nTotal events found: {len(events)}")
        return events

    except Exception as e:
        print(f"Error: {str(e)}")
        logging.error(f"Error scraping MUSE: {str(e)}")
        return []


def scrape_pangea(base_url):
    """PANGEAのスケジュールをスクレイピング"""
    logger = logging.getLogger(__name__)
    logger.info("=== PANGEA Scraping Start ===")
    events = []

    try:
        session = init_session()
        schedule_url = f"{base_url}/schedule/"
        logger.info(f"Fetching schedule page: {schedule_url}")

        try:
            response = make_request(session, schedule_url)
            schedule_soup = BeautifulSoup(response.text, 'html.parser')
            
            # イベントリンクの収集
            event_urls = set()  # 重複を避けるためにsetを使用
            for link in schedule_soup.find_all('a', href=True):
                href = link['href']
                if '/live/' in href:
                    # 相対パスを完全なURLに変換
                    full_url = href if base_url in href else f"{base_url}{href.lstrip('/')}"
                    event_urls.add(full_url)

            logger.info(f"Found {len(event_urls)} unique event URLs")

            # 各イベントページの処理
            for event_url in event_urls:
                try:
                    logger.debug(f"Processing event URL: {event_url}")
                    detail_response = make_request(session, event_url)
                    detail_soup = BeautifulSoup(detail_response.text, 'html.parser')

                    # 日付情報の取得
                    live_mom = detail_soup.find('p', class_='live_mom')
                    live_day = detail_soup.find('p', class_='live_day')
                    
                    if not live_mom or not live_day:
                        logger.debug("Date information not found")
                        continue

                    # 日付の解析
                    date_text = f"{live_mom.text.strip()}/{live_day.text.strip()}"
                    try:
                        date = parse_date(date_text)
                    except ValueError as e:
                        logger.debug(f"Date parsing failed: {str(e)}")
                        continue

                    # タイトル情報の取得
                    title_span = detail_soup.find('span', class_='pangea-color', 
                                                style=lambda x: x and 'font-weight: 400' in x)
                    title = title_span.text.strip() if title_span else ""
                    logger.debug(f"Found title: {title}")

                    # アーティスト情報の取得と処理
                    artist_div = detail_soup.find('div', class_='hrbox')
                    if artist_div and artist_div.find('span', class_='badge-info'):
                        artist_container = artist_div.find('div')
                        if artist_container and artist_container.find('p'):
                            artist_text = artist_container.find('p').text.strip()
                            logger.debug(f"Found artist text: {artist_text}")
                            
                            # アーティスト名の分割と整形
                            artists = []
                            for line in artist_text.split('\n'):
                                parts = re.split(r'[/、]', line)
                                for part in parts:
                                    artist_name = clean_artist_name(part.strip(), debug=False)
                                    if artist_name and len(artist_name) > 1:  # 1文字以下は除外
                                        artists.append(artist_name)
                            
                            # イベントの作成
                            for artist in artists:
                                event = create_event(
                                    date=date,
                                    day_jp=get_weekday_jp(date),
                                    artist=artist,
                                    title=title,
                                    url=event_url,
                                    venue='PANGEA',
                                    note=''
                                )
                                events.append(event)
                                logger.debug(f"Created event: {event}")

                except Exception as e:
                    logger.error(f"Error processing detail page {event_url}: {str(e)}", exc_info=True)
                    continue

        except Exception as e:
            logger.error(f"Error accessing schedule page: {str(e)}", exc_info=True)
            return []

        logger.info(f"Total events found: {len(events)}")
        return events

    except Exception as e:
        logger.error(f"Error scraping PANGEA: {str(e)}", exc_info=True)
        return []



def scrape_venue(url):
    try:
        if 'fireloop.net' in url:
            return scrape_fireloop(url)
        elif 'para-dice.net' in url:
            return scrape_paradice(url)
        elif any(domain in url for domain in ['vijon.jp', 'bangboo.jp', 'clubdrop.jp', 'osaka-varon.jp', 'osaka-zeela.jp']):
            return scrape_vijon_system(url)
        elif 'club-quattro.com' in url:
            return scrape_quattro(url)
        elif 'rocktown.jp' in url:
            return scrape_rocktown(url)
        elif 'knave.co.jp' in url:
            return scrape_knave(url)
        elif 'namba-hatch.com' in url:
            return scrape_hatch(url)
        elif 'muse-live.com' in url:
            return scrape_muse(url)
        elif 'livepangea.com' in url:
            return scrape_pangea(url)
        return []
    except Exception as e:
        logging.error(f"Error scraping {url}: {str(e)}")
        return []

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
    
    all_events = []
    for url in venues:
        events = scrape_venue(url)
        all_events.extend(events)
        
    save_data(all_events)

if __name__ == "__main__":
    main()
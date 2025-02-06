# venues.py
VENUE_CONFIGS = {
    'fireloop': {
        'name': '寺田町Fireloop',
        'url': 'https://fireloop.net/schedule_now.shtml',
        'area': 'osaka',
    },
    'vijon': {
        'name': '北堀江club vijon',
        'url': 'https://vijon.jp',
        'area': 'osaka',
        'scraping_type': 'vijon_system'  # スクレイピング方式を示す
    },
    'bangboo': {
        'name': '梅田BANGBOO',
        'url': 'https://bangboo.jp',
        'area': 'osaka',
        'scraping_type': 'vijon_system'
    },
    'drop': {
        'name': 'アメリカ村DROP',
        'url': 'https://clubdrop.jp',
        'area': 'osaka',
        'scraping_type': 'vijon_system'
    },
    'varon': {
        'name': 'VARON',
        'url': 'https://osaka-varon.jp',
        'area': 'osaka',
        'scraping_type': 'vijon_system'
    },
    'zeela': {
        'name': 'Zeela',
        'url': 'https://osaka-zeela.jp',
        'area': 'osaka',
        'scraping_type': 'vijon_system'
    }
}
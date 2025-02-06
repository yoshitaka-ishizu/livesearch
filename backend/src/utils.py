def create_event(date, day_jp, artist, title, url, venue, note=''):
    """イベントオブジェクトを作成するヘルパー関数（共通化）"""
    return {
        'date': date,
        'day': day_jp,
        'artist': artist,
        'title': title,
        'url': url,
        'venue': venue,
        'note': note
    }
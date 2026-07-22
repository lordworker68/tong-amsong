#!/usr/bin/env python3
# 통암송 Spotify(Anchor RSS) 자동 수집 — "성경읽는 희석이" 쇼(meslap 팟캐스트 네트워크 공유)
# 에피소드 제목에서 성경책 이름을 추출해 책별로 묶어 최신 N개씩 노출(책이 계속 늘어나도 자동 대응)
# 출력: /var/www/tong/data/spotify.json
import json, re, time, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

FEED_URL = "https://anchor.fm/s/103728a7c/podcast/rss"
SHOW_HREF = "https://open.spotify.com/show/0BNrpFEwm3BVXTv8EAL4Og"
SHOW_TITLE = "성경읽는 희석이"
SHOW_DESC = "매일 성경 본문을 소리 내어 읽어주는 통암송 팟캐스트입니다."
OUT = "/var/www/tong/data/spotify.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
MAX_FETCH = 600          # RSS 전체를 훑어 책 분류(오래된 책이 빠지지 않도록, 피드 총량보다 넉넉하게)
PER_BOOK = 2             # 책마다 대표로 보여줄 개수
BOOK_RE = re.compile(r"\|\s*([가-힣]{2,6})\s*(\d+)\s*(장|편)")


def fetch(url, tries=4):
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
            time.sleep(2)
    raise RuntimeError("fetch fail %s: %s" % (url, last))


def parse_duration(s):
    if not s:
        return "-"
    s = s.strip()
    parts = s.split(":")
    if len(parts) == 3:
        h, m, sec = int(parts[0]), int(parts[1]), int(parts[2])
        m = h * 60 + m
        return "%d:%02d" % (m, sec)
    elif len(parts) == 2:
        return s
    return "-"


def parse_date(pubdate_str):
    try:
        dt = parsedate_to_datetime(pubdate_str)
        return dt.strftime("%Y년 %-m월 %d일")
    except Exception:
        return ""


def main():
    xml_data = fetch(FEED_URL)
    root = ET.fromstring(xml_data)

    books = []            # [{name, episodes:[...]}] — 첫 등장(최신 발행) 순서 유지
    book_index = {}       # name -> index in books

    for item in root.findall(".//item")[:MAX_FETCH]:
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        pubdate = (item.findtext("pubDate") or "").strip()
        duration = item.findtext("{http://www.itunes.com/dtds/podcast-1.0.dtd}duration") or ""
        link = (item.findtext("link") or "").strip()
        enclosure = item.find("enclosure")
        audio_url = enclosure.get("url", "") if enclosure is not None else ""

        m = BOOK_RE.search(title)
        book_name = m.group(1) if m else "기타"
        chapter = int(m.group(2)) if m else 0

        if book_name not in book_index:
            book_index[book_name] = len(books)
            books.append({"name": book_name, "episodes": []})
        entry = books[book_index[book_name]]
        # 책마다 전체 장을 모아뒀다가 아래에서 1장부터 순서대로 PER_BOOK개만 추림
        entry["episodes"].append({
            "chapter": chapter,
            "title": title,
            "date": parse_date(pubdate),
            "time": parse_duration(duration),
            "href": link,
            "audio": audio_url,
        })

    for b in books:
        b["episodes"].sort(key=lambda e: e["chapter"])   # 1장 -> 오름차순
        b["episodes"] = b["episodes"][:PER_BOOK]
        for e in b["episodes"]:
            del e["chapter"]

    total = sum(len(b["episodes"]) for b in books)
    out = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "show": {"title": SHOW_TITLE, "desc": SHOW_DESC, "show_href": SHOW_HREF},
        "books": books,
    }
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    import os
    os.replace(tmp, OUT)
    print("OK: %d books, %d episodes -> %s" % (len(books), total, OUT))


if __name__ == "__main__":
    main()

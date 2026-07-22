#!/usr/bin/env python3
# 통암송 YouTube 자동 수집 — 채널 RSS(API키 불필요), meslap fetch_youtube.py와 동일 패턴
# 출력: /var/www/tong/data/youtube.json
import json, re, time, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone

CHANNEL_ID = "UCaNna1M5rWO5FZcKfAX6OCw"  # 성경 통암송 · Scripture In Song (@tongamsong)
FEED = "https://www.youtube.com/feeds/videos.xml?channel_id=" + CHANNEL_ID
OUT = "/var/www/tong/data/youtube.json"
MAX = 16
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "media": "http://search.yahoo.com/mrss/"}


def fetch(url, tries=4):
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read()
            if len(data) > 500:
                return data
            last = "short body %d" % len(data)
        except Exception as e:
            last = str(e)
        time.sleep(2)
    raise RuntimeError("fetch failed: %s" % last)


def main():
    xml_data = fetch(FEED)
    root = ET.fromstring(xml_data)
    videos = []
    for entry in root.findall("a:entry", NS)[:MAX]:
        vid = entry.findtext("yt:videoId", default="", namespaces=NS)
        title = entry.findtext("a:title", default="", namespaces=NS)
        published = entry.findtext("a:published", default="", namespaces=NS)
        media_group = entry.find("media:group", NS)
        thumb = ""
        if media_group is not None:
            thumb_el = media_group.find("media:thumbnail", NS)
            if thumb_el is not None:
                thumb = thumb_el.get("url", "")
        if not vid:
            continue
        videos.append({
            "id": vid,
            "title": title,
            "url": "https://www.youtube.com/watch?v=" + vid,
            "thumb": thumb or ("https://i.ytimg.com/vi/%s/hqdefault.jpg" % vid),
            "published": published,
            "is_short": bool(re.search(r"#\s*shorts", title, re.IGNORECASE)),
        })

    out = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "videos": videos,
    }
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    import os
    os.replace(tmp, OUT)
    print("OK: %d videos -> %s" % (len(videos), OUT))


if __name__ == "__main__":
    main()

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

def _short(vid, title, date, lang):
    return {"id": vid, "title": title,
            "url": "https://www.youtube.com/watch?v=" + vid,
            "thumb": "https://i.ytimg.com/vi/%s/hqdefault.jpg" % vid,
            "published": date + "T00:00:00+00:00",
            "is_short": True, "lang": lang}

def _long(vid, title, date, lang):
    return {"id": vid, "title": title,
            "url": "https://www.youtube.com/watch?v=" + vid,
            "thumb": "https://i.ytimg.com/vi/%s/hqdefault.jpg" % vid,
            "published": date + "T00:00:00+00:00",
            "is_short": False, "lang": lang}

# RSS 최신 15개 한계를 보완 — 언어별 8개씩 유지용 하드코딩 보충 목록
# (RSS에 이미 있는 ID는 자동으로 중복 제거됨)
EXTRA_VIDEOS = [
    # ── 영어 롱폼 ──────────────────────────────────────────────
    _long("JlD_GU7BsMM", "잠언 1:7~19 영어(KJV) 솔로 — 말씀의 선율 통암송", "2026-08-11", "en"),

    # ── 한국어 솔로 쇼츠 1:26~32 (1:33은 RSS에 있음) ────────
    _short("ewaCU0qpxMU", "잠언 1:32 성경암송 | 심비에 새기는 잠언 통암송 #Shorts", "2026-09-13", "ko"),
    _short("iglWVP9042E", "잠언 1:31 성경암송 | 심비에 새기는 잠언 통암송 #Shorts", "2026-09-12", "ko"),
    _short("HhGSV8cxt9o", "잠언 1:30 성경암송 | 심비에 새기는 잠언 통암송 #Shorts", "2026-09-11", "ko"),
    _short("49wz19I5PVc", "잠언 1:29 성경암송 | 심비에 새기는 잠언 통암송 #Shorts", "2026-09-10", "ko"),
    _short("do32R1H7TIU", "잠언 1:28 성경암송 | 심비에 새기는 잠언 통암송 #Shorts", "2026-09-09", "ko"),
    _short("IRz56itP_Zw", "잠언 1:27 성경암송 | 심비에 새기는 잠언 통암송 #Shorts", "2026-09-08", "ko"),
    _short("6a9Pv-k8ilA", "잠언 1:26 성경암송 | 심비에 새기는 잠언 통암송 #Shorts", "2026-09-07", "ko"),

    # ── 영어 솔로 쇼츠 1:26~31 (1:32~33은 RSS에 있음) ───────
    _short("Uzeq0p-CibA", "잠언 1:32 영어 성경암송 | 말씀의 선율 잠언 통암송 #Shorts", "2026-09-13", "en"),
    _short("rsiaP7vy0M4", "잠언 1:31 영어 성경암송 | 말씀의 선율 잠언 통암송 #Shorts", "2026-09-12", "en"),
    _short("4fSOgeLnGgM", "잠언 1:30 영어 성경암송 | 말씀의 선율 잠언 통암송 #Shorts", "2026-09-11", "en"),
    _short("4ZH83OoXGdc", "잠언 1:29 영어 성경암송 | 말씀의 선율 잠언 통암송 #Shorts", "2026-09-10", "en"),
    _short("DCFnW6ezfcY", "잠언 1:28 영어 성경암송 | 말씀의 선율 잠언 통암송 #Shorts", "2026-09-09", "en"),
    _short("1dXCrxsUm5Q", "잠언 1:27 영어 성경암송 | 말씀의 선율 잠언 통암송 #Shorts", "2026-09-08", "en"),
    _short("HGEDaoQl0_g", "잠언 1:26 영어 성경암송 | 말씀의 선율 잠언 통암송 #Shorts", "2026-09-07", "en"),

    # ── 히브리어 솔로 쇼츠 1:26~32 (1:33은 RSS에 있음) ───
    _short("7bpUs_cOZGU", "잠언 1:32 히브리어 성경암송 | 첫소리 잠언 통암송 #Shorts", "2026-09-29", "he"),
    _short("IGvPApynxSc", "잠언 1:31 히브리어 성경암송 | 첫소리 잠언 통암송 #Shorts", "2026-09-28", "he"),
    _short("NrygyhdVoN8", "잠언 1:30 히브리어 성경암송 | 첫소리 잠언 통암송 #Shorts", "2026-09-28", "he"),
    _short("7_2SX7uu_6c", "잠언 1:29 히브리어 성경암송 | 첫소리 잠언 통암송 #Shorts", "2026-09-27", "he"),
    _short("6BH4me_cHAA", "잠언 1:28 히브리어 성경암송 | 첫소리 잠언 통암송 #Shorts", "2026-09-27", "he"),
    _short("-C0T2pchzyQ", "잠언 1:27 히브리어 성경암송 | 첫소리 잠언 통암송 #Shorts", "2026-09-26", "he"),
    _short("FLTjxwjmLpI", "잠언 1:26 히브리어 성경암송 | 첫소리 잠언 통암송 #Shorts", "2026-09-26", "he"),

    # 세겹줄은 RSS에서 이미 충분히 수집됨 (최신 ~9개)
]


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
    seen_ids = set()
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
        seen_ids.add(vid)
        videos.append({
            "id": vid,
            "title": title,
            "url": "https://www.youtube.com/watch?v=" + vid,
            "thumb": thumb or ("https://i.ytimg.com/vi/%s/hqdefault.jpg" % vid),
            "published": published,
            "is_short": bool(re.search(r"#\s*shorts", title, re.IGNORECASE)),
        })

    # 보충 영상 — RSS에 없는 경우에만 추가
    for extra in EXTRA_VIDEOS:
        if extra["id"] not in seen_ids:
            videos.append(extra)

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

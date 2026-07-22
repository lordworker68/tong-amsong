#!/usr/bin/env python3
"""
Threads 장기 토큰 주간 갱신 (60일 만료, WIA 가이드 16장).
페이지 토큰(인스타/페북 공용)은 만료가 없어 갱신 불필요.
크론: 주 1회. 마지막 갱신 후 7일 미만이면 건너뜀 — 실패해도 60일 창 안에 여러 번 재시도되어 안전.
"""
import json
import os
import requests
from datetime import datetime, timezone, timedelta

CONFIG_PATH = "/var/www/tong/data/meta-config.json"
THREADS_GRAPH = "https://graph.threads.net/v1.0"


def log(msg):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {msg}")


def save_config(cfg):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)
    try:
        import grp
        gid = grp.getgrnam("www-data").gr_gid
        os.chown(CONFIG_PATH, -1, gid)
    except (KeyError, PermissionError):
        pass
    os.chmod(CONFIG_PATH, 0o660)


def main():
    if not os.path.exists(CONFIG_PATH):
        log("설정 파일 없음 — 아직 연결 전")
        return
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)

    th = cfg.get("threads", {})
    token = th.get("access_token")
    if not token:
        log("Threads 미연결 — 건너뜀")
        return

    last = th.get("last_refreshed_at") or th.get("issued_at")
    if last:
        last_dt = datetime.fromisoformat(last)
        if datetime.now(timezone.utc) - last_dt < timedelta(days=7):
            log(f"최근 갱신({last}) 7일 미만 — 건너뜀")
            return

    r = requests.get(f"{THREADS_GRAPH}/refresh_access_token", params={
        "grant_type": "th_refresh_token", "access_token": token,
    })
    if r.status_code != 200:
        log(f"갱신 실패: {r.text}")
        return

    d = r.json()
    th["access_token"] = d["access_token"]
    th["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=d.get("expires_in", 5184000))).isoformat()
    th["last_refreshed_at"] = datetime.now(timezone.utc).isoformat()
    cfg["threads"] = th
    save_config(cfg)
    log("Threads 토큰 갱신 완료 (다시 60일)")


if __name__ == "__main__":
    main()

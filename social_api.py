#!/usr/bin/env python3
"""
tongamsong 소셜 자동배포 API — 인스타 릴스 · 페북 릴스 · Threads
WIA Music 실전 가이드(social-guide-36075bef9f2d6139.html)의 절차를 그대로 이식.
Graph API v25.0. 설정은 /var/www/tong/data/meta-config.json (0660, group www-data)에 저장.
"""
from flask import Flask, request, jsonify
import json
import os
import time
import requests

app = Flask(__name__)

CONFIG_PATH = "/var/www/tong/data/meta-config.json"
GRAPH = "https://graph.facebook.com/v25.0"
THREADS_GRAPH = "https://graph.threads.net/v1.0"


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(cfg):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)
    # os.replace가 임시파일 소유권을 그대로 가져와 그룹이 깨지는 문제(WIA 가이드 16장) 방지
    try:
        import grp
        gid = grp.getgrnam("www-data").gr_gid
        os.chown(CONFIG_PATH, -1, gid)
    except (KeyError, PermissionError):
        pass
    os.chmod(CONFIG_PATH, 0o660)


def mask(s):
    if not s or len(s) < 10:
        return "••••" if s else None
    return f"{s[:6]}••••••{s[-4:]}"


# ---------- 상태 ----------

@app.route("/social-api/status", methods=["GET"])
def status():
    cfg = load_config()
    fb = cfg.get("facebook", {})
    th = cfg.get("threads", {})
    return jsonify({
        "facebook": {
            "connected": bool(fb.get("page_token")),
            "page_id": fb.get("page_id"),
            "page_name": fb.get("page_name"),
            "ig_user_id": fb.get("ig_user_id"),
            "ig_username": fb.get("ig_username"),
            "page_token": mask(fb.get("page_token")),
            "connected_at": fb.get("connected_at"),
        },
        "threads": {
            "connected": bool(th.get("access_token")),
            "user_id": th.get("user_id"),
            "access_token": mask(th.get("access_token")),
            "expires_at": th.get("expires_at"),
            "last_refreshed_at": th.get("last_refreshed_at"),
        },
    })


# ---------- Facebook / Instagram 연결 (가이드 6~11장) ----------

@app.route("/social-api/connect-meta", methods=["POST"])
def connect_meta():
    body = request.get_json(force=True)
    app_id = body.get("app_id", "").strip()
    app_secret = body.get("app_secret", "").strip()
    short_token = body.get("short_token", "").strip()
    page_id_hint = body.get("page_id_hint", "").strip()

    if not (app_id and app_secret and short_token):
        return jsonify({"error": "app_id, app_secret, short_token 필요"}), 400

    # 1) 단기 토큰 → 장기 사용자 토큰 교환
    r = requests.get(f"{GRAPH}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token,
    })
    if r.status_code != 200:
        return jsonify({"error": "토큰 교환 실패", "detail": r.json()}), 400
    long_user_token = r.json()["access_token"]

    # 2) 관리 페이지 목록 조회 (가이드 11장 함정②③: business_management 없으면
    #    /me/accounts가 0개일 수 있음 → page_id_hint로 개별 조회 우회)
    page = None
    r = requests.get(f"{GRAPH}/me/accounts", params={
        "fields": "id,name,access_token,instagram_business_account",
        "access_token": long_user_token,
    })
    accounts = r.json().get("data", [])
    if accounts:
        page = accounts[0] if not page_id_hint else next(
            (a for a in accounts if a["id"] == page_id_hint), accounts[0]
        )
    elif page_id_hint:
        r2 = requests.get(f"{GRAPH}/{page_id_hint}", params={
            "fields": "id,name,access_token,instagram_business_account",
            "access_token": long_user_token,
        })
        if r2.status_code == 200:
            page = r2.json()

    if not page:
        return jsonify({
            "error": "페이지를 찾지 못했습니다. 가이드 11장 함정②③ 참고 "
                     "(로그인창 '자산 선택'에서 페이지 체크했는지, page_id_hint로 재시도해보세요)",
            "raw_accounts_response": r.json(),
        }), 400

    ig_user_id = None
    ig_username = None
    iba = page.get("instagram_business_account")
    if iba:
        ig_user_id = iba["id"]
        r3 = requests.get(f"{GRAPH}/{ig_user_id}", params={
            "fields": "username", "access_token": page["access_token"],
        })
        ig_username = r3.json().get("username")

    cfg = load_config()
    from datetime import datetime, timezone
    cfg["facebook"] = {
        "app_id": app_id,
        "app_secret": app_secret,
        "page_id": page["id"],
        "page_name": page["name"],
        "page_token": page["access_token"],
        "ig_user_id": ig_user_id,
        "ig_username": ig_username,
        "connected_at": datetime.now(timezone.utc).isoformat(),
    }
    save_config(cfg)

    warn = None if ig_user_id else (
        "페이지는 연결됐지만 Instagram 계정이 안 잡힙니다 — 가이드 11장 함정④: "
        "facebook.com/settings/?tab=linked_profiles 에서 이 페이지와 인스타 계정을 "
        "명시적으로 '연결'했는지 확인하세요."
    )
    return jsonify({"ok": True, "page_name": page["name"], "ig_username": ig_username, "warning": warn})


# ---------- Threads 연결 (가이드 10장) ----------

@app.route("/social-api/connect-threads", methods=["POST"])
def connect_threads():
    body = request.get_json(force=True)
    app_id = body.get("app_id", "").strip()
    app_secret = body.get("app_secret", "").strip()
    tester_token = body.get("tester_token", "").strip()

    if not tester_token:
        return jsonify({"error": "tester_token 필요 (개발자 콘솔 '사용자 토큰 생성기'에서 발급)"}), 400

    r = requests.get(f"{THREADS_GRAPH}/me", params={
        "fields": "id,username", "access_token": tester_token,
    })
    if r.status_code != 200:
        return jsonify({"error": "토큰 검증 실패", "detail": r.json()}), 400
    me = r.json()

    cfg = load_config()
    from datetime import datetime, timezone, timedelta
    cfg["threads"] = {
        "app_id": app_id,
        "app_secret": app_secret,
        "user_id": me["id"],
        "username": me.get("username"),
        "access_token": tester_token,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=5184000)).isoformat(),
        "last_refreshed_at": None,
    }
    save_config(cfg)
    return jsonify({"ok": True, "username": me.get("username")})


# ---------- 발행 (가이드 12~13장) ----------

def publish_instagram_reels(ig_user_id, page_token, video_url, caption):
    r = requests.post(f"{GRAPH}/{ig_user_id}/media", data={
        "media_type": "REELS", "video_url": video_url, "caption": caption,
        "access_token": page_token,
    })
    if r.status_code != 200:
        return {"ok": False, "step": "create", "detail": r.json()}
    creation_id = r.json()["id"]

    deadline = time.time() + 120
    while time.time() < deadline:
        rs = requests.get(f"{GRAPH}/{creation_id}", params={
            "fields": "status_code,status", "access_token": page_token,
        }).json()
        if rs.get("status_code") == "FINISHED":
            break
        if rs.get("status_code") == "ERROR":
            return {"ok": False, "step": "poll", "detail": rs}
        time.sleep(5)
    else:
        return {"ok": False, "step": "poll_timeout"}

    rp = requests.post(f"{GRAPH}/{ig_user_id}/media_publish", data={
        "creation_id": creation_id, "access_token": page_token,
    })
    if rp.status_code != 200:
        return {"ok": False, "step": "publish", "detail": rp.json()}
    return {"ok": True, "media_id": rp.json().get("id")}


def publish_facebook_reels(page_id, page_token, video_url, caption):
    r1 = requests.post(f"{GRAPH}/{page_id}/video_reels", data={
        "upload_phase": "start", "access_token": page_token,
    })
    if r1.status_code != 200:
        return {"ok": False, "step": "start", "detail": r1.json()}
    d = r1.json()
    video_id, upload_url = d["video_id"], d["upload_url"]

    # rupload.facebook.com — 그래프 API와 다른 호스트 (가이드 13장)
    r2 = requests.post(upload_url, headers={
        "Authorization": f"OAuth {page_token}",
        "file_url": video_url,
    })
    if r2.status_code != 200 or not r2.json().get("success", True):
        return {"ok": False, "step": "upload", "detail": r2.text}

    r3 = requests.post(f"{GRAPH}/{page_id}/video_reels", data={
        "upload_phase": "finish", "video_id": video_id,
        "video_state": "PUBLISHED", "description": caption,
        "access_token": page_token,
    })
    if r3.status_code != 200:
        return {"ok": False, "step": "finish", "detail": r3.json()}
    return {"ok": True, "video_id": video_id}


def publish_threads(user_id, token, video_url, caption):
    r1 = requests.post(f"{THREADS_GRAPH}/{user_id}/threads", data={
        "media_type": "VIDEO", "video_url": video_url, "text": caption,
        "access_token": token,
    })
    if r1.status_code != 200:
        return {"ok": False, "step": "create", "detail": r1.json()}
    creation_id = r1.json()["id"]

    time.sleep(30)  # 가이드 13장: 발행 전 최소 30초 대기 필수

    r2 = requests.post(f"{THREADS_GRAPH}/{user_id}/threads_publish", data={
        "creation_id": creation_id, "access_token": token,
    })
    if r2.status_code != 200:
        return {"ok": False, "step": "publish", "detail": r2.json()}
    return {"ok": True, "media_id": r2.json().get("id")}


@app.route("/social-api/publish", methods=["POST"])
def publish():
    body = request.get_json(force=True)
    video_url = body.get("video_url", "").strip()
    caption = body.get("caption", "").strip()
    platforms = body.get("platforms", ["instagram", "facebook", "threads"])

    if not video_url.startswith("https://"):
        return jsonify({"error": "video_url은 공개 HTTPS 주소여야 합니다 (Meta가 직접 fetch)"}), 400

    cfg = load_config()
    fb = cfg.get("facebook", {})
    th = cfg.get("threads", {})
    result = {}

    if "instagram" in platforms:
        if not fb.get("ig_user_id"):
            result["instagram"] = {"ok": False, "step": "not_connected"}
        else:
            result["instagram"] = publish_instagram_reels(fb["ig_user_id"], fb["page_token"], video_url, caption)

    if "facebook" in platforms:
        if not fb.get("page_token"):
            result["facebook"] = {"ok": False, "step": "not_connected"}
        else:
            result["facebook"] = publish_facebook_reels(fb["page_id"], fb["page_token"], video_url, caption)

    if "threads" in platforms:
        if not th.get("access_token"):
            result["threads"] = {"ok": False, "step": "not_connected"}
        else:
            result["threads"] = publish_threads(th["user_id"], th["access_token"], video_url, caption)

    return jsonify(result)


# ---------- 발행 한도 조회 (가이드 15장) ----------

@app.route("/social-api/limits", methods=["GET"])
def limits():
    cfg = load_config()
    fb = cfg.get("facebook", {})
    th = cfg.get("threads", {})
    out = {}
    if fb.get("ig_user_id"):
        r = requests.get(f"{GRAPH}/{fb['ig_user_id']}/content_publishing_limit", params={
            "fields": "config,quota_usage", "access_token": fb["page_token"],
        })
        out["instagram"] = r.json()
    if th.get("user_id"):
        r = requests.get(f"{THREADS_GRAPH}/{th['user_id']}/threads_publishing_limit", params={
            "fields": "config,quota_usage", "access_token": th["access_token"],
        })
        out["threads"] = r.json()
    return jsonify(out)


if __name__ == "__main__":
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    app.run(host="127.0.0.1", port=8091)

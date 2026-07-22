#!/bin/bash
# 통암송 사이트 git 자동 백업 — 매일 새벽 4시 crontab 실행
# 변경사항 있을 때만 커밋하고 GitHub(origin/main)로 push
set -euo pipefail
cd /var/www/tong

git add -A

if git diff --cached --quiet; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] 변경사항 없음, 스킵"
  exit 0
fi

git commit -m "auto backup $(date '+%Y-%m-%d %H:%M')"
git push origin main
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 자동 백업 완료"

#!/bin/bash
# deploy.sh — deploy/ 폴더 동기화 + Cloudflare Workers 배포 한 줄로
set -e

cd "$(dirname "$0")"

# 1) deploy/ 폴더 동기화
echo "📦 deploy/ 폴더 동기화..."
cp index.html deploy/index.html
cp data/ulsan_schools.json deploy/data/ulsan_schools.json
cp data/ulsan_districts.json deploy/data/ulsan_districts.json
cp data/ulsan_school_zones.json deploy/data/ulsan_school_zones.json

# 중학교/고등학교 학구 파일
if [ -f data/ulsan_middle_school_zones.json ]; then
  cp data/ulsan_middle_school_zones.json deploy/data/ulsan_middle_school_zones.json
fi
if [ -f data/ulsan_high_school_zones.json ]; then
  cp data/ulsan_high_school_zones.json deploy/data/ulsan_high_school_zones.json
fi

# dev_projects 파일이 있으면 같이 복사
if [ -f data/ulsan_dev_projects.json ]; then
  cp data/ulsan_dev_projects.json deploy/data/ulsan_dev_projects.json
fi

echo "✅ 동기화 완료"

# 2) Cloudflare 배포
echo "🚀 Cloudflare 배포 중..."
npx wrangler deploy --name=schoolmap --assets deploy/ --compatibility-date 2026-04-05

echo "✅ 배포 완료: https://ulsanschool.kr"

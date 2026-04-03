"""
NEIS 교육정보 개방 포털에서 울산 학교 데이터를 가져와 기존 데이터를 보강하는 스크립트.

사용법:
  1. https://open.neis.go.kr 에서 무료 API 키 발급
  2. 환경변수 설정: set NEIS_API_KEY=발급받은키
  3. 실행: python scripts/fetch_neis.py

기능:
  - NEIS API에서 울산 전체 학교 기본정보 조회
  - 도로명주소, 전화번호, 홈페이지 등 메타데이터 보강
  - 누락 학교는 Nominatim 지오코딩으로 좌표 확보 후 추가
  - data/ulsan_schools.json 업데이트
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

NEIS_BASE = "https://open.neis.go.kr/hub/schoolInfo"
CLASS_INFO_BASE = "https://open.neis.go.kr/hub/classInfo"
ULSAN_CODE = "H10"  # 울산광역시교육청
DATA_PATH = Path(__file__).parent.parent / "data" / "ulsan_schools.json"


def fetch_neis_schools(api_key, page_size=100):
    """NEIS API에서 울산 학교 전체 목록 조회"""
    all_rows = []
    page = 1

    while True:
        url = (
            f"{NEIS_BASE}?Type=json&pIndex={page}&pSize={page_size}"
            f"&ATPT_OFCDC_SC_CODE={ULSAN_CODE}&KEY={api_key}"
        )
        print(f"  페이지 {page} 요청중...")

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        info = data.get("schoolInfo")
        if not info or len(info) < 2:
            break

        rows = info[1].get("row", [])
        if not rows:
            break

        all_rows.extend(rows)
        total = info[0]["head"][0]["list_total_count"]
        print(f"  -> {len(rows)}개 수신 (누적: {len(all_rows)}/{total})")

        if len(all_rows) >= total:
            break
        page += 1

    return all_rows


def fetch_class_info(api_key, school_code):
    """classInfo API로 학교의 학년별 학급 수 조회 (2026학년도)"""
    url = (
        f"{CLASS_INFO_BASE}?Type=json&pIndex=1&pSize=500"
        f"&ATPT_OFCDC_SC_CODE={ULSAN_CODE}"
        f"&SD_SCHUL_CODE={school_code}"
        f"&AY=2026&KEY={api_key}"
    )
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"    classInfo 요청 실패: {e}")
        return None, None

    info = data.get("classInfo")
    if not info or len(info) < 2:
        return None, None

    rows = info[1].get("row", [])
    if not rows:
        return None, None

    # 학년별 학급 수 집계
    grade_counts = {}
    for row in rows:
        grade = row.get("GRADE", "").strip()
        if grade:
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

    total = sum(grade_counts.values())
    return total, grade_counts


def normalize_homepage(url):
    """홈페이지 URL 정규화: http:// 접두사 보장, 빈 URL 제거"""
    if not url or url in ("http://", "https://"):
        return ""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url
    return url


def geocode_address(address):
    """Nominatim으로 주소 -> 좌표 변환"""
    query = urllib.parse.quote(address)
    url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "UlsanSchoolMap/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            results = json.loads(resp.read())
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"    지오코딩 실패: {e}")
    return None, None


def neis_to_school(neis, school_id, lat, lng):
    """NEIS row를 학교 객체로 변환"""
    name = neis["SCHUL_NM"]
    school_type = neis.get("SCHUL_KND_SC_NM") or "기타"
    address = ((neis.get("ORG_RDNMA") or "") + " " + (neis.get("ORG_RDNDA") or "")).strip()

    district = guess_district_from_address(address, lat, lng)

    school = {
        "name": name,
        "type": school_type,
        "lat": round(lat, 7),
        "lng": round(lng, 7),
        "address": address,
        "district": district,
        "id": school_id,
        "phone": neis.get("ORG_TELNO") or "",
        "homepage": normalize_homepage((neis.get("HMPG_ADRES") or "").strip()),
        "eng_name": neis.get("ENG_SCHUL_NM") or "",
        "coedu": neis.get("COEDU_SC_NM") or "",
        "founding_type": neis.get("FOND_SC_NM") or "",
        "school_code": neis.get("SD_SCHUL_CODE") or "",
    }
    hs = neis.get("HS_SC_NM")
    if hs and hs.strip():
        school["hs_type"] = hs.strip()
    return school


def guess_district_from_address(address, lat, lng):
    """주소 텍스트 또는 좌표로 구/군 추정"""
    if "중구" in address:
        return "중구"
    if "남구" in address:
        return "남구"
    if "동구" in address:
        return "동구"
    if "북구" in address:
        return "북구"
    if "울주군" in address:
        return "울주군"
    # 좌표 기반 fallback
    if lat and lng:
        return get_district_by_coords(lat, lng)
    return "울주군"


def get_district_by_coords(lat, lng):
    """좌��� 기반 구/군 추정"""
    if lng >= 129.39 and 35.46 <= lat <= 35.57:
        return "동구"
    if lat >= 129.30 and lat >= 35.59 and lng <= 129.45:
        return "북구"
    if 35.545 <= lat < 35.59 and 129.285 <= lng <= 129.37:
        return "중구"
    if 35.50 <= lat < 35.555 and 129.26 <= lng <= 129.35:
        return "남구"
    if 35.525 <= lat < 35.56 and 129.24 <= lng < 129.30:
        return "남구"
    return "울주군"


def enrich_dataset(neis_rows, api_key):
    """기존 JSON에 NEIS 데이터 병합 + 누락 학교 추가 + 학급정보 수집"""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    # NEIS 데이터를 학교명 기준 딕셔너리로
    neis_map = {}
    for row in neis_rows:
        name = row["SCHUL_NM"]
        neis_map[name] = row

    # 1단계: 기존 학교 보강
    existing_names = set()
    matched = 0
    for school in dataset["schools"]:
        existing_names.add(school["name"])
        neis = neis_map.get(school["name"])
        if neis:
            matched += 1
            school["address"] = ((neis.get("ORG_RDNMA") or "") + " " + (neis.get("ORG_RDNDA") or "")).strip()
            school["phone"] = neis.get("ORG_TELNO") or ""
            hp = (neis.get("HMPG_ADRES") or "").strip()
            hp = normalize_homepage(hp)
            school["homepage"] = hp
            school["eng_name"] = neis.get("ENG_SCHUL_NM") or ""
            school["coedu"] = neis.get("COEDU_SC_NM") or ""
            school["founding_type"] = neis.get("FOND_SC_NM") or ""
            school["school_code"] = neis.get("SD_SCHUL_CODE") or ""
            # 주소에서 구/군 재분류
            school["district"] = guess_district_from_address(
                school["address"], school["lat"], school["lng"]
            )
            if neis.get("HS_SC_NM") and neis["HS_SC_NM"].strip():
                school["hs_type"] = neis["HS_SC_NM"].strip()

    print(f"\n기존 학교 보강: {matched}/{len(dataset['schools'])}개 매칭")

    # 2단계: 누락된 학교 추가 (지오코딩으로 좌표 확보)
    missing = [row for name, row in neis_map.items() if name not in existing_names]
    print(f"누락 학교: {len(missing)}개 -> 지오코딩 후 추가")

    next_id = max(s["id"] for s in dataset["schools"]) + 1
    added = 0
    failed = 0

    for row in missing:
        name = row["SCHUL_NM"]
        address = (row.get("ORG_RDNMA") or "")
        print(f"  [{added+failed+1}/{len(missing)}] {name} ... ", end="", flush=True)

        lat, lng = geocode_address(address)
        if lat is None:
            # 학교명으로 재시도
            lat, lng = geocode_address(f"{name} 울산")

        if lat is not None:
            school = neis_to_school(row, next_id, lat, lng)
            dataset["schools"].append(school)
            next_id += 1
            added += 1
            print(f"OK ({lat:.5f}, {lng:.5f})")
        else:
            failed += 1
            print("FAIL - 좌표 확보 실패")

        time.sleep(1)  # Nominatim 사용 정책 (1요청/초)

    print(f"\n추가 완료: {added}개 성공, {failed}개 실패")

    # 3단계: 학급정보 수집 (classInfo API)
    schools_with_code = [s for s in dataset["schools"] if s.get("school_code")]
    print(f"\n=== 학급정보 수집 시작 ({len(schools_with_code)}개 학교) ===")
    class_success = 0
    for i, school in enumerate(schools_with_code, 1):
        code = school["school_code"]
        print(f"  [{i}/{len(schools_with_code)}] {school['name']} ({code}) ... ", end="", flush=True)
        total, by_grade = fetch_class_info(api_key, code)
        if total is not None:
            school["total_classes"] = total
            school["classes_by_grade"] = by_grade
            class_success += 1
            print(f"OK ({total}학급)")
        else:
            print("데이터 없음")
        time.sleep(0.1)  # API 부하 방지

    print(f"\n학급정보 수집 완료: {class_success}/{len(schools_with_code)}개 성공")

    # 4단계: 메타데이터 갱신
    dataset["schools"].sort(key=lambda x: (x["type"], x["name"]))
    for i, s in enumerate(dataset["schools"], 1):
        s["id"] = i

    types = {}
    districts = {}
    for s in dataset["schools"]:
        types[s["type"]] = types.get(s["type"], 0) + 1
        districts[s["district"]] = districts.get(s["district"], 0) + 1

    dataset["metadata"]["total_count"] = len(dataset["schools"])
    dataset["metadata"]["types"] = types
    dataset["metadata"]["districts"] = districts

    print(f"\n최종 학교 수: {len(dataset['schools'])}")
    for t, c in sorted(types.items()):
        print(f"  {t}: {c}")

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"\n저장 완료: {DATA_PATH}")


def main():
    api_key = os.environ.get("NEIS_API_KEY")
    if not api_key:
        print("=" * 60)
        print("NEIS API 키가 필요합니다!")
        print()
        print("1. https://open.neis.go.kr 접속")
        print("2. 인증키 신청 (네이버/카카오 로그인)")
        print("3. 환경변수 설정:")
        print("   set NEIS_API_KEY=발급받은키")
        print("4. 다시 실행:")
        print("   python scripts/fetch_neis.py")
        print("=" * 60)
        sys.exit(1)

    print("=== NEIS 울산 학교 데이터 수집 시작 ===")
    rows = fetch_neis_schools(api_key)
    print(f"\n총 {len(rows)}개 학교 수신 완료")
    enrich_dataset(rows, api_key)


if __name__ == "__main__":
    main()

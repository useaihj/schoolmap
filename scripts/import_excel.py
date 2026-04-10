"""
5개 엑셀 파일을 통합하여 ulsan_schools.json을 생성하는 스크립트.

소스:
  1. 초등학교현황.xlsx / 중학교현황.xlsx / 고등학교현황.xlsx → 학급·학생·교직원 등 전체 데이터
  2. 울산학교주소위도경도.xlsx → 주소, 위도, 경도 (위도/경도는 보정된 값)
  3. 울산학교개교일우편번호전화번호팩스번호홈페이지.xlsx → 개교일, 우편번호, 전화, 팩스, 홈페이지
"""

import json
from pathlib import Path

import openpyxl

BASE_DIR = Path(__file__).parent.parent
DATA_PATH = BASE_DIR / "data" / "ulsan_schools.json"


# ── 1) 현황 엑셀 읽기 ──────────────────────────────────────────

def read_elementary(path):
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    schools = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        name = (row[4] or "").strip()
        if not name:
            continue
        cbg = {str(g): int(row[9 + g - 1] or 0) for g in range(1, 7)}
        sbg = {str(g): int(row[17 + g - 1] or 0) for g in range(1, 7)}
        sc = int(row[15] or 0)
        schools.append({
            "name": name,
            "type": "초등학교",
            "founding_type": (row[3] or "").strip(),
            "school_code": (row[5] or "").strip(),
            "district": (row[6] or "").strip(),
            "staff_count": int(row[7] or 0),
            "total_classes": int(row[8] or 0),
            "classes_by_grade": cbg,
            "special_classes": sc,
            "total_students": int(row[16] or 0),
            "students_by_grade": sbg,
        })
    return schools


def read_middle(path):
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    schools = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        name = (row[2] or "").strip()
        if not name:
            continue
        cbg = {str(g): int(row[6 + g - 1] or 0) for g in range(1, 4)}
        sbg = {str(g): int(row[10 + g - 1] or 0) for g in range(1, 4)}
        sc = int(row[9] or 0)
        tc = sum(cbg.values()) + sc
        ts = sum(sbg.values())
        schools.append({
            "name": name,
            "type": "중학교",
            "founding_type": (row[1] or "").strip(),
            "school_code": (row[3] or "").strip(),
            "district": (row[4] or "").strip(),
            "coedu": (row[5] or "").strip(),
            "total_classes": tc,
            "classes_by_grade": cbg,
            "special_classes": sc,
            "total_students": ts,
            "students_by_grade": sbg,
        })
    return schools


def read_high(path):
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    schools = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        name = (row[3] or "").strip()
        if not name:
            continue
        cbg = {str(g): int(row[7 + g - 1] or 0) for g in range(1, 4)}
        sbg = {str(g): int(row[11 + g - 1] or 0) for g in range(1, 4)}
        sc = int(row[10] or 0)
        tc = sum(cbg.values()) + sc
        ts = sum(sbg.values())
        schools.append({
            "name": name,
            "type": "고등학교",
            "founding_type": (row[2] or "").strip(),
            "district": (row[4] or "").strip(),
            "hs_category": (row[5] or "").strip(),
            "coedu": (row[6] or "").strip(),
            "total_classes": tc,
            "classes_by_grade": cbg,
            "special_classes": sc,
            "total_students": ts,
            "students_by_grade": sbg,
        })
    return schools


# ── 2) 위치 엑셀 읽기 ──────────────────────────────────────────

def read_location(path):
    """울산학교주소위도경도.xlsx → {학교명: {address, lat, lng}}"""
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    loc = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        name = (row[0] or "").strip() if row[0] else ""
        if not name:
            continue
        addr_val = row[7] if len(row) > 7 else ""
        lat_val = row[8] if len(row) > 8 else 0
        lng_val = row[9] if len(row) > 9 else 0
        loc[name] = {
            "address": str(addr_val).strip() if addr_val else "",
            "lat": float(lat_val) if lat_val not in (None, "") else 0,
            "lng": float(lng_val) if lng_val not in (None, "") else 0,
        }
    return loc


# ── 3) 연락처 엑셀 읽기 ────────────────────────────────────────

def normalize_homepage(url):
    if not url or url.strip() in ("", "http://", "https://"):
        return ""
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url
    return url


def read_contact(path):
    """울산학교개교일...홈페이지.xlsx → {학교명: {founded, zipcode, phone, fax, homepage}}"""
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    info = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        name = (row[1] or "").strip()
        if not name:
            continue
        info[name] = {
            "founded": str(row[2] or "").strip(),
            "zipcode": str(row[3] or "").strip(),
            "phone": str(row[4] or "").strip(),
            "fax": str(row[5] or "").strip(),
            "homepage": normalize_homepage(str(row[6] or "")),
        }
    return info


# ── 4) 이름 매칭 헬퍼 ──────────────────────────────────────────

def find_match(name, lookup):
    """학교명 매칭: 직접 → 울산 접두사 추가 → 울산 제거"""
    if name in lookup:
        return lookup[name]
    if ("울산" + name) in lookup:
        return lookup["울산" + name]
    short = name.replace("울산", "", 1)
    if short != name and short in lookup:
        return lookup[short]
    return None


# ── 5) 통계 계산 ───────────────────────────────────────────────

def calc_stats(s):
    tc = s["total_classes"]
    sc = s["special_classes"]
    ts = s["total_students"]
    regular = tc - sc
    s["avg_students_per_class"] = round(ts / regular, 1) if regular > 0 else 0

    avg_bg = {}
    for g, cnt in s["classes_by_grade"].items():
        stu = s["students_by_grade"].get(g, 0)
        avg_bg[g] = round(stu / cnt, 1) if cnt > 0 else 0
    s["avg_students_per_class_by_grade"] = avg_bg


# ── main ────────────────────────────────────────────────────────

def main():
    # 1) 현황 엑셀 → 245개 학교 기본 데이터
    elem = read_elementary(BASE_DIR / "초등학교현황.xlsx")
    mid = read_middle(BASE_DIR / "중학교현황.xlsx")
    high = read_high(BASE_DIR / "고등학교현황.xlsx")
    all_schools = elem + mid + high
    print(f"현황 엑셀: {len(all_schools)}개 (초{len(elem)} + 중{len(mid)} + 고{len(high)})")

    # 2) 위치 엑셀 → 주소/위도/경도
    loc = read_location(BASE_DIR / "울산학교주소위도경도.xlsx")
    print(f"위치 데이터: {len(loc)}개")

    loc_ok, loc_miss = 0, []
    for s in all_schools:
        m = find_match(s["name"], loc)
        if m:
            s["address"] = m["address"]
            s["lat"] = round(m["lat"], 7)
            s["lng"] = round(m["lng"], 7)
            loc_ok += 1
        else:
            s["address"] = ""
            s["lat"] = 0
            s["lng"] = 0
            loc_miss.append(s["name"])
    print(f"  위치 매칭: {loc_ok}/{len(all_schools)}")
    if loc_miss:
        print(f"  미매칭: {loc_miss}")

    # 3) 연락처 엑셀 → 개교일/우편번호/전화/팩스/홈페이지
    contact = read_contact(BASE_DIR / "울산학교개교일우편번호전화번호팩스번호홈페이지.xlsx")
    print(f"연락처 데이터: {len(contact)}개")

    ct_ok, ct_miss = 0, []
    for s in all_schools:
        m = find_match(s["name"], contact)
        if m:
            s.update(m)
            ct_ok += 1
        else:
            s.update({"founded": "", "zipcode": "", "phone": "", "fax": "", "homepage": ""})
            ct_miss.append(s["name"])
    print(f"  연락처 매칭: {ct_ok}/{len(all_schools)}")
    if ct_miss:
        print(f"  미매칭: {ct_miss}")

    # 4) 통계 계산
    for s in all_schools:
        calc_stats(s)

    # 5) 정렬 및 ID 부여
    all_schools.sort(key=lambda x: (x["type"], x["name"]))
    for i, s in enumerate(all_schools, 1):
        s["id"] = i

    # 6) 메타데이터
    types, districts = {}, {}
    for s in all_schools:
        types[s["type"]] = types.get(s["type"], 0) + 1
        districts[s["district"]] = districts.get(s["district"], 0) + 1

    dataset = {
        "metadata": {
            "title": "울산광역시 학교 데이터",
            "source": "학교급별현황 + 학교위치표준데이터 + NEIS 학교정보",
            "coordinate_system": "WGS84 (EPSG:4326)",
            "last_updated": "2026-04-03",
            "total_count": len(all_schools),
            "types": types,
            "districts": districts,
        },
        "schools": all_schools,
    }

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"\n=== 최종 ===")
    print(f"총 {len(all_schools)}개 학교")
    for t, c in sorted(types.items()):
        print(f"  {t}: {c}")
    print(f"저장: {DATA_PATH}")


if __name__ == "__main__":
    main()

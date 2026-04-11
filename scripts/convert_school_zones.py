"""
초/중/고 학구 SHP → 울산 필터링 + WGS84 변환 + 공간 조인 → GeoJSON

출력:
  data/ulsan_school_zones.json         (초등 통학구역 + 초등학교 리스트)
  data/ulsan_middle_school_zones.json  (중학교 학구/학교군 + 초/중 학교 리스트)
  data/ulsan_high_school_zones.json    (고등학교 학교군 + 고등학교 리스트)

그리고 data/ulsan_schools.json 의 각 학교에 다음 필드 추가:
  - elem_zone  (초등학교만, 통학구역 이름)
  - middle_zone (초/중학교, 진학/소속 중학구·학교군 이름)
  - high_zone  (고등학교만, 소속 학교군 이름)

원본 (data/shp/):
  초등학교통학구역.{shp,dbf,shx,prj,cpg}
  중학교학교군.{shp,dbf,shx,prj,cpg}
  고등학교학교군.{shp,dbf,shx,prj,cpg}

좌표계: EPSG:5186 → WGS84(EPSG:4326)
울산 필터: SD_CD == '31'
"""
import json
import os
import re
import sys
import shapefile
from pyproj import Transformer
from shapely.geometry import Point, shape as shp_shape

ULSAN_SD_CD = '31'
SRC_CRS = 'EPSG:5186'
DST_CRS = 'EPSG:4326'
SCHOOLS_JSON = 'data/ulsan_schools.json'

# (SHP 파일 스템, 출력 JSON 경로, 학구 종류) — SHP 원본은 data/shp/ 에 있음
SHP_DIR = 'data/shp'
JOBS = [
    (f'{SHP_DIR}/초등학교통학구역',  'data/ulsan_school_zones.json',         'elem'),
    (f'{SHP_DIR}/중학교학교군',      'data/ulsan_middle_school_zones.json',  'middle'),
    (f'{SHP_DIR}/고등학교학교군',    'data/ulsan_high_school_zones.json',    'high'),
]


def transform_ring(ring, transformer):
    """[[x,y], ...] -> [[lng,lat], ...]"""
    return [list(transformer.transform(x, y)) for x, y in ring]


def shp_geom_to_geojson(shape, transformer):
    """shapefile Shape → GeoJSON geometry

    여러 ring을 포함 관계(containment) 기반으로 outer/hole 판정.
    - 나를 포함하는 더 큰 ring이 있으면 → 나는 그 ring의 hole
    - 없으면 → 나는 outer
    winding order에 의존하지 않음 (SHP 데이터가 winding을 제대로 지키지 않는 경우 대비).
    """
    from shapely.geometry import Polygon

    parts = list(shape.parts) + [len(shape.points)]
    rings = []
    for i in range(len(parts) - 1):
        pts = shape.points[parts[i]:parts[i+1]]
        rings.append(transform_ring(pts, transformer))

    if not rings:
        return None

    # 각 ring → 임시 Polygon
    temp_polys = []
    for r in rings:
        try:
            temp_polys.append(Polygon(r))
        except Exception:
            temp_polys.append(None)

    n = len(rings)
    parent = [None] * n  # hole의 부모 outer 인덱스

    for i in range(n):
        if temp_polys[i] is None:
            continue
        # 나를 포함하는 가장 작은 ring 찾기
        best = None
        best_area = float('inf')
        for j in range(n):
            if i == j or temp_polys[j] is None:
                continue
            try:
                if temp_polys[j].contains(temp_polys[i]):
                    if temp_polys[j].area < best_area:
                        best = j
                        best_area = temp_polys[j].area
            except Exception:
                pass
        parent[i] = best

    # outer_idx → [hole_idx, ...]
    outer_holes = {}
    for i in range(n):
        if parent[i] is None:
            outer_holes.setdefault(i, [])
    for i in range(n):
        if parent[i] is not None and parent[i] in outer_holes:
            outer_holes[parent[i]].append(i)

    polygons = []
    for outer_idx, hole_idxs in outer_holes.items():
        outer = rings[outer_idx]
        holes = [rings[h] for h in hole_idxs]
        polygons.append((outer, holes))

    if not polygons:
        return {'type': 'Polygon', 'coordinates': [rings[0]]}

    if len(polygons) == 1:
        outer, holes = polygons[0]
        return {'type': 'Polygon', 'coordinates': [outer] + holes}
    else:
        coords = [[o] + hs for o, hs in polygons]
        return {'type': 'MultiPolygon', 'coordinates': coords}


def convert_one(shp_stem, out_path, zone_kind, schools):
    if not os.path.exists(shp_stem + '.shp'):
        print(f'  [건너뜀] {shp_stem}.shp 없음')
        return None

    transformer = Transformer.from_crs(SRC_CRS, DST_CRS, always_xy=True)
    sf = shapefile.Reader(shp_stem, encoding='euc-kr')

    # 울산 초등학교 이름 세트 (공동통학구역 경계 검사용)
    ulsan_elem_names = set(s['name'] for s in schools if s.get('type') == '초등학교')

    features = []
    excluded_gongdong = []
    for sr in sf.shapeRecords():
        d = sr.record.as_dict()
        if str(d.get('SD_CD', '')) != ULSAN_SD_CD:
            continue
        zone_name = d.get('HAKGUDO_NM', '')
        zone_gb = d.get('HAKGUDO_GB', '')

        # 공동통학구역인 경우: 이름에 섞인 학교가 모두 울산에 있어야 포함
        if zone_kind == 'elem' and zone_gb == '1':
            prefix = zone_name.split('공동')[0]
            shorts = re.findall(r'.+?초', prefix)
            all_ulsan = True
            for sh in shorts:
                # 정확 매칭 우선
                exact = sh + '등학교'
                if exact in ulsan_elem_names:
                    continue
                # 접두사 매칭 (분교장 등)
                if any(u.startswith(sh) for u in ulsan_elem_names):
                    continue
                all_ulsan = False
                break
            if not all_ulsan:
                excluded_gongdong.append(zone_name)
                continue

        geom = shp_geom_to_geojson(sr.shape, transformer)
        if geom is None:
            continue
        # 면적 계산 (정규화: square degrees)
        try:
            area = shp_shape(geom).area
        except Exception:
            area = 0
        props = {
            'name': zone_name,
            'gb': zone_gb,
            'edu_nm': d.get('EDU_NM', '',),
            'sgg_cd': d.get('SGG_CD', ''),
            'area': area,
        }
        features.append({
            'type': 'Feature',
            'geometry': geom,
            'properties': props,
        })

    if excluded_gongdong:
        print(f'  [제외] 울산 외 학교 포함 공동통학구역: {excluded_gongdong}')

    # 학교별 zone 매핑
    zone_to_schools = {f['properties']['name']: {'elementary': [], 'middle': [], 'high': []} for f in features}
    school_to_zone = {}

    def find_ulsan_elem(short):
        """'개운초' → '개운초등학교' (정확 매칭 우선)"""
        exact = short + '등학교'
        if exact in ulsan_elem_names:
            return exact
        for u in sorted(ulsan_elem_names):  # 결정적 순서
            if u.startswith(short):
                return u
        return None

    if zone_kind == 'elem':
        # 초등 통학구역은 폴리곤 이름 기반으로 학교 매칭 (공간 조인 X)
        # 이유: 폴리곤이 "도넛 구멍" 형태로 중첩될 수 있어 공간 조인 불가
        #       (예: 개운초통학구역 안에 두왕초통학구역이 있음)
        # 일반 이름 파싱으로 매칭이 어려운 예외(분교장 등)
        MANUAL_MAP = {
            '상북초소호분교통학구역': '상북초등학교소호분교장',
        }
        for f in features:
            p = f['properties']
            name = p['name']
            matched = []
            if name in MANUAL_MAP:
                matched = [MANUAL_MAP[name]]
            elif p.get('gb') == '1':
                # 공동통학구역: "공동" 앞 prefix에서 학교 약칭 여러 개 추출
                prefix = name.split('공동')[0]
                for short in re.findall(r'.+?초', prefix):
                    full = find_ulsan_elem(short)
                    if full and full not in matched:
                        matched.append(full)
            else:
                # 단일: "XX초통학구역" → XX초 → XX초등학교
                if name.endswith('통학구역'):
                    short = name[:-len('통학구역')]
                    full = find_ulsan_elem(short)
                    if full:
                        matched = [full]
            zone_to_schools[name]['elementary'] = matched
            for sch in matched:
                # 단일 학구는 그 학교만, 공동은 첫 학교만 "자기 학구"
                if sch not in school_to_zone:
                    school_to_zone[sch] = name
    else:
        # 중/고 학구·학교군: 공간 조인 (이름으로 학교 추정 불가)
        shapely_polys = [(f['properties']['name'], shp_shape(f['geometry'])) for f in features]
        target_types = {
            'middle': {'초등학교', '중학교'},
            'high':   {'고등학교'},
        }[zone_kind]

        for s in schools:
            if s.get('type') not in target_types:
                continue
            pt = Point(s['lng'], s['lat'])
            for zname, poly in shapely_polys:
                if poly.contains(pt):
                    if s['type'] == '초등학교':
                        zone_to_schools[zname]['elementary'].append(s['name'])
                    elif s['type'] == '중학교':
                        zone_to_schools[zname]['middle'].append(s['name'])
                    elif s['type'] == '고등학교':
                        zone_to_schools[zname]['high'].append(s['name'])
                    if s['name'] not in school_to_zone:
                        school_to_zone[s['name']] = zname

    # 폴리곤 properties에 학교 리스트 저장
    for f in features:
        lists = zone_to_schools[f['properties']['name']]
        f['properties']['elementary_schools'] = sorted(lists['elementary'])
        f['properties']['middle_schools'] = sorted(lists['middle'])
        f['properties']['high_schools'] = sorted(lists['high'])

    geojson = {'type': 'FeatureCollection', 'features': features}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False)

    size_kb = os.path.getsize(out_path) / 1024
    print(f'  [OK] {shp_stem}: {len(features)}개 → {out_path} ({size_kb:.0f} KB)')
    return school_to_zone


def main():
    print('=== 학구 SHP → GeoJSON 변환 (공간 조인 포함) ===')

    # 학교 데이터 로드
    with open(SCHOOLS_JSON, encoding='utf-8') as f:
        schools_data = json.load(f)
    schools = schools_data['schools']

    # 각 zone 타입별로 변환 + 조인 결과 수집
    school_to_elem = {}
    school_to_middle = {}
    school_to_high = {}

    for stem, out, kind in JOBS:
        print(f'\n▶ {stem}')
        m = convert_one(stem, out, kind, schools) or {}
        if kind == 'elem':
            school_to_elem = m
        elif kind == 'middle':
            school_to_middle = m
        elif kind == 'high':
            school_to_high = m

    # 각 학교에 zone 정보 역할당
    print('\n▶ ulsan_schools.json 학교별 zone 필드 추가')
    elem_updated = mid_updated = high_updated = 0
    for s in schools:
        name = s['name']
        t = s.get('type')
        # elem_zone: 초등학교의 자기 통학구역
        if t == '초등학교' and name in school_to_elem:
            s['elem_zone'] = school_to_elem[name]
            elem_updated += 1
        else:
            s.pop('elem_zone', None)
        # middle_zone: 초/중학교 → 속한 중학구·학교군
        if t in ('초등학교', '중학교') and name in school_to_middle:
            s['middle_zone'] = school_to_middle[name]
            mid_updated += 1
        else:
            s.pop('middle_zone', None)
        # high_zone: 고등학교 → 속한 학교군
        if t == '고등학교' and name in school_to_high:
            s['high_zone'] = school_to_high[name]
            high_updated += 1
        else:
            s.pop('high_zone', None)

    with open(SCHOOLS_JSON, 'w', encoding='utf-8') as f:
        json.dump(schools_data, f, ensure_ascii=False, indent=2)
    print(f'  [OK] elem_zone {elem_updated}, middle_zone {mid_updated}, high_zone {high_updated} 학교 업데이트')

    print('\n완료.')


if __name__ == '__main__':
    main()

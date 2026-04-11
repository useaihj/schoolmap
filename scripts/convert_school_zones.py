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

원본:
  초등학교통학구역.{shp,dbf,shx,prj,cpg}
  중학교학교군.{shp,dbf,shx,prj,cpg}
  고등학교학교군.{shp,dbf,shx,prj,cpg}

좌표계: EPSG:5186 → WGS84(EPSG:4326)
울산 필터: SD_CD == '31'
"""
import json
import os
import sys
import shapefile
from pyproj import Transformer
from shapely.geometry import Point, shape as shp_shape

ULSAN_SD_CD = '31'
SRC_CRS = 'EPSG:5186'
DST_CRS = 'EPSG:4326'
SCHOOLS_JSON = 'data/ulsan_schools.json'

# (SHP 파일명, 출력 JSON 경로, 학구 종류)
JOBS = [
    ('초등학교통학구역',   'data/ulsan_school_zones.json',         'elem'),
    ('중학교학교군',       'data/ulsan_middle_school_zones.json',  'middle'),
    ('고등학교학교군',     'data/ulsan_high_school_zones.json',    'high'),
]


def transform_ring(ring, transformer):
    """[[x,y], ...] -> [[lng,lat], ...]"""
    return [list(transformer.transform(x, y)) for x, y in ring]


def shp_geom_to_geojson(shape, transformer):
    """shapefile Shape → GeoJSON geometry (Polygon 또는 MultiPolygon)"""
    # shape.parts는 각 ring의 시작 인덱스
    parts = list(shape.parts) + [len(shape.points)]
    rings = []
    for i in range(len(parts) - 1):
        pts = shape.points[parts[i]:parts[i+1]]
        rings.append(transform_ring(pts, transformer))

    if len(rings) == 0:
        return None
    elif len(rings) == 1:
        return {'type': 'Polygon', 'coordinates': [rings[0]]}
    else:
        # 여러 ring: 단순하게 각 ring을 별도 Polygon으로 취급 (MultiPolygon)
        # 구멍(hole) 판단은 복잡하므로, 학구/학교군 데이터는 보통 단일 외곽 링 기반이라 안전함
        return {
            'type': 'MultiPolygon',
            'coordinates': [[ring] for ring in rings]
        }


def convert_one(shp_stem, out_path, zone_kind, schools):
    if not os.path.exists(shp_stem + '.shp'):
        print(f'  [건너뜀] {shp_stem}.shp 없음')
        return None

    transformer = Transformer.from_crs(SRC_CRS, DST_CRS, always_xy=True)
    sf = shapefile.Reader(shp_stem, encoding='euc-kr')

    features = []
    for sr in sf.shapeRecords():
        d = sr.record.as_dict()
        if str(d.get('SD_CD', '')) != ULSAN_SD_CD:
            continue
        geom = shp_geom_to_geojson(sr.shape, transformer)
        if geom is None:
            continue
        props = {
            'name': d.get('HAKGUDO_NM', ''),
            'gb': d.get('HAKGUDO_GB', ''),
            'edu_nm': d.get('EDU_NM', ''),
            'sgg_cd': d.get('SGG_CD', ''),
        }
        features.append({
            'type': 'Feature',
            'geometry': geom,
            'properties': props,
        })

    # 공간 조인: 학교 좌표가 어느 폴리곤에 속하는지
    # zone_kind에 따라 어떤 학교를 매칭할지 결정
    shapely_polys = [(f['properties']['name'], shp_shape(f['geometry'])) for f in features]

    # 학교 타입별 매칭 대상 정의
    #  - elem   폴리곤: 초등학교만 매칭
    #  - middle 폴리곤: 초등학교 + 중학교 매칭
    #  - high   폴리곤: 고등학교만 매칭
    target_types = {
        'elem':   {'초등학교'},
        'middle': {'초등학교', '중학교'},
        'high':   {'고등학교'},
    }[zone_kind]

    # 각 폴리곤별 학교 리스트
    zone_to_schools = {f['properties']['name']: {'elementary': [], 'middle': [], 'high': []} for f in features}
    # 각 학교별 속한 zone 이름 (첫 매칭)
    school_to_zone = {}

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

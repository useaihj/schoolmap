# 작업 워크플로우
1. 요청을 받으면 반영 계획을 먼저 정리해서 보여줄 것
2. 승인을 받은 후에 실행할 것
3. 정적 사이트 관련 파일 수정 후에는 빌드/배포까지 자동 진행

# 울산 학교 찾기

울산광역시 245개 학교(초등 124, 중학 64, 고등 57)를 지도에 표시하는 인터랙티브 웹앱.
5개 구/군: 중구, 남구, 동구, 북구, 울주군. 데이터 기준: 2026년 2월.

## 기술 스택

- 프론트엔드: 순수 HTML/CSS/JS 단일 파일 (`index.html`, 1141줄), 프레임워크 없음
- 지도: Leaflet.js + OpenStreetMap 타일 + Leaflet.markercluster
- 차트: Chart.js (대시보드)
- 데이터: JSON 3개 (학교, 행정구역, 통학구역)
- 로컬 서버: `python serve.py` → http://localhost:8080
- 배포: Cloudflare Pages (`deploy/` 폴더 업로드)

## 파일 구조

```
index.html                — UI + 전체 로직 (단일 파일, CSS+JS 인라인)
serve.py                  — Python 로컬 서버 (포트 8080)
data/
  ulsan_schools.json      — 245개 학교 데이터 (import_excel.py로 생성)
  ulsan_districts.json    — 5개 구/군 행정구역 경계 GeoJSON (2025년 행정동 합침)
  ulsan_school_zones.json — 126개 초등학교 통학구역 GeoJSON (공식 SHP 변환)
scripts/
  import_excel.py         — 엑셀 5개 → ulsan_schools.json 통합 변환
  build_dataset.py        — 이전 데이터 빌드 스크립트
  fetch_neis.py           — NEIS API 데이터 수집 스크립트
deploy/                   — Cloudflare Pages 배포용 (index.html + data/ 3개 JSON)
```

### 원본 데이터 파일 (프로젝트 루트)

| 파일 | 내용 |
|------|------|
| 초등학교현황.xlsx | 초등학교 학급/학생 현황 |
| 중학교현황.xlsx | 중학교 학급/학생 현황 |
| 고등학교현황.xlsx | 고등학교 학급/학생 현황 |
| 울산학교주소위도경도.xls | 주소, 위도, 경도 |
| 울산학교개교일우편번호전화번호팩스번호홈페이지.xlsx | 개교일, 우편번호, 전화, 팩스, 홈페이지 |
| 초등학교통학구역.shp (+cpg,dbf,prj,qmd,shx) | 전국 초등학교 통학구역 SHP (EPSG:5186, EUC-KR) |

## 데이터 파이프라인

### 학교 데이터
엑셀 5개 → `python scripts/import_excel.py` → `data/ulsan_schools.json`

학교 필드: name, type, founding_type, district, hs_category, coedu, total_classes, classes_by_grade, special_classes, total_students, students_by_grade, address, lat, lng, founded, zipcode, phone, fax, homepage, avg_students_per_class, avg_students_per_class_by_grade

이름 매칭: 직접 → "울산" 접두사 추가 → "울산" 제거 순으로 시도.

### 행정구역 경계
GitHub vuski/admdongkor (2025년 1월) → 울산 55개 행정동 추출 → shapely unary_union으로 5개 구/군 합침 → `data/ulsan_districts.json`

### 통학구역
초등학교통학구역.shp (전국 7123개) → pyshp+pyproj로 울산(SD_CD=31) 126개 필터링 + EPSG:5186→WGS84 변환 → `data/ulsan_school_zones.json`

## 주요 기능

### 검색/필터/정렬
- 학교명 텍스트 검색 (부분 매칭, 하이라이트)
- 유형 필터 (전체/초등/중학/고등) — 헤더 버튼 + 모바일 칩
- 구/군 드롭다운 필터
- 정렬: 이름순, 학생수, 학급수, 학급당 학생수 (각 오름/내림)
- 빈 상태 안내 + 필터 초기화 버튼

### 지도
- pill 형태 마커, 색상 구분 (초=녹색 #059669, 중=파란색 #2563EB, 고=주황색 #EA580C)
- 마커 클러스터링 (maxClusterRadius: 40, 줌 14에서 해제)
- 줌 14 이상 시 학교 약칭 표시 (예: "울산강동초")
- 구/군 필터 시 해당 행정구역 경계 폴리곤 오버레이
- 초등학교 선택 시 통학구역 폴리곤 표시 (녹색 실선, fillOpacity: 0.2)

### 마커 표기 규칙 (shortName 함수)
- "울산" 유지 (생략하지 않음)
- "여자상업" → "여상" (접미사 "고" 없이 종결)
- "상업" → "상", "공업" → "공", "여자" → "여", "스포츠과학" → "스포츠"

### 사이드바 ↔ 지도 연동
- 카드 hover → 마커 강조, 마커 hover → 카드 강조
- **사이드바 클릭** → 지도 이동 + 마커 강조 + 통학구역 표시 (팝업 없음)
- **지도 마커 클릭** → 위와 동일 + 팝업 표시 (PC) / 바텀 시트 표시 (모바일)
- 팝업 닫아도 선택 상태 + 통학구역 유지
- 필터(유형/구/군) 변경 → 통학구역 + 선택 상태 초기화

### 학교 비교
- 카드 체크박스로 2~3개 선택 → 하단 비교 바 → 비교 모달 (테이블)
- 비교 항목: 학교명, 유형, 설립, 구/군, 공학, 고교유형, 학생수, 학급수, 학급당 학생수, 개교일, 주소

### 대시보드
- 헤더 "대시보드" 버튼 → 모달 (Chart.js)
- 5개 차트: 구별 학교 분포(스택 바), 학교 유형 비율(도넛), 구별 학급당 평균 학생수(바), 설립 유형(도넛), 학생수 상위 15개(가로 바)

### 모바일 바텀 시트 (768px 이하)
- 마커/사이드바 클릭 시 Leaflet 팝업 대신 바텀 시트(60vh)로 학교 정보 표시
- 고정 높이, 내부 스크롤, ✕ 버튼 또는 오버레이 터치로 닫기
- 전화번호 tel: 링크 (클릭 시 전화 가능, 팩스는 링크 없음)
- CSS transition: transform + pointer-events (display:none 사용 안 함)
- 모바일에서는 bindPopup 하지 않음 (팝업 플래시 방지)
- 관련 함수: `isMobile()`, `createSheetContent(s)`, `openBottomSheet(school)`, `closeBottomSheet()`

### 반응형
- 768px 이하: 지도(상) + 목록(하) 세로 배치, 모바일 필터 칩

## JS 아키텍처 (index.html 내 IIFE)

### 전역 상태
allSchools, filteredSchools, markers, activeMarker, hoveredMarker, currentType, currentDistrict, currentSearch, currentSort, compareList, districtGeoData, districtLayer, schoolZoneData, schoolZoneLayer, clusterGroup, dashCharts

### 핵심 함수
- `applyFilters(skipFitBounds)` — 필터링 + 정렬 + 렌더링 오케스트레이션
- `renderMarkers(skipFitBounds)` — 클러스터 그룹으로 마커 렌더링
- `renderList()` — 사이드바 목록 렌더링 (체크박스 포함)
- `selectSchool(id, openPopup)` — 학교 선택 (openPopup: 마커 클릭 시 true, 사이드바 클릭 시 false)
- `createIcon(type, state, school)` — 줌 레벨별 pill 마커 생성
- `shortName(name, type)` — 학교 약칭 생성
- `showDistrictBoundary(districtName)` — 행정구역 경계 표시/해제
- `showSchoolZone(school)` / `clearSchoolZone()` — 통학구역 표시/해제
- `isMobile()` — 모바일 판별 (768px 이하)
- `createSheetContent(s)` — 모바일 바텀 시트 내용 생성
- `openBottomSheet(school)` / `closeBottomSheet()` — 모바일 바텀 시트 열기/닫기
- `openDashboard()` / `closeDashboard()` — 대시보드 모달
- `openCompare()` / `closeCompare()` / `toggleCompare(id)` — 학교 비교

## 실행

```bash
python serve.py
# http://localhost:8080 접속
```

## 배포

Cloudflare Pages: `deploy/` 폴더를 Upload and Deploy.

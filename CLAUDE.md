# 작업 워크플로우
1. 요청을 받으면 반영 계획을 먼저 정리해서 보여줄 것
2. 승인을 받은 후에 실행할 것
3. 정적 사이트 관련 파일 수정 후에는 빌드/배포까지 자동 진행

# 울산 학교 찾기

울산광역시 252개 학교를 지도에 표시하는 인터랙티브 웹앱.
유형: 초등 124, 중학 64, 고등 57, 특수학교 4, 각종학교 3.
5개 구/군: 중구, 남구, 동구, 북구, 울주군. 데이터 기준: 2026년 2월.

## 기술 스택

- 프론트엔드: 순수 HTML/CSS/JS 단일 파일 (`index.html`), 프레임워크 없음
- 지도: 카카오맵 JavaScript API
- 데이터: JSON 4개 (학교, 행정구역, 통학구역, 개발사업)
- 로컬 서버: `python serve.py` → http://localhost:8080
- 배포: Cloudflare Workers via `deploy.sh` (wrangler deploy → https://ulsanschool.kr)

## 파일 구조

```
index.html                — UI + 전체 로직 (단일 파일, CSS+JS 인라인)
serve.py                  — Python 로컬 서버 (포트 8080)
deploy.sh                 — Cloudflare Workers 배포 스크립트
data/
  ulsan_schools.json      — 252개 학교 데이터 (import_excel.py로 생성)
  ulsan_districts.json    — 5개 구/군 행정구역 경계 GeoJSON
  ulsan_school_zones.json — 126개 초등학교 통학구역 GeoJSON (공식 SHP 변환)
  ulsan_dev_projects.json — 개발사업 125건 데이터
scripts/
  import_excel.py         — 엑셀 7개(xlsx) → ulsan_schools.json 통합 변환 (openpyxl)
  add_school.py           — 새 학교를 위치+연락처 엑셀에 동시 추가 (CLI)
  remove_school.py        — 학교를 양쪽 엑셀에서 제거 (CLI)
  migrate_xls_to_xlsx.py  — 일회성 마이그레이션 (실행 완료, 참고용 보관)
  build_dataset.py        — 이전 데이터 빌드 스크립트
  fetch_neis.py           — NEIS API 데이터 수집 스크립트
deploy/                   — Cloudflare Workers 배포용 (index.html + data/ JSON)
```

### 원본 데이터 파일 (프로젝트 루트)

| 파일 | 내용 |
|------|------|
| 초등학교현황.xlsx | 초등학교 학급/학생 현황 (124개교) |
| 중학교현황.xlsx | 중학교 학급/학생 현황 (64개교) |
| 고등학교현황.xlsx | 고등학교 학급/학생 현황 (57개교) |
| 특수학교현황.xlsx | 특수학교 현황 (4개교). 학년 체계: 유치원/초등/중/고/전공과 5단계 |
| 각종학교현황.xlsx | 각종학교 현황 (3개교). 학년 체계: 1/2/3학년 |
| 울산학교주소위도경도.xlsx | 주소, 위도, 경도 ⚠️ 위도/경도는 공식 원본이 아니라 210건 이상이 보정된 값. 원본은 git 히스토리(커밋 a66f2ea의 .xls) 참고. 보정 경위는 커밋 742c105, d528a44 참고 |
| 울산학교개교일우편번호전화번호팩스번호홈페이지.xlsx | 개교일, 우편번호, 전화, 팩스, 홈페이지 (252개 + 기타) |
| 초등학교통학구역.shp (+cpg,dbf,prj,qmd,shx) | 전국 초등학교 통학구역 SHP (EPSG:5186, EUC-KR) |

## 데이터 파이프라인

### 학교 데이터
엑셀 7개 → `python scripts/import_excel.py` → `data/ulsan_schools.json`

학교 유형별 reader: `read_elementary`, `read_middle`, `read_high`, `read_special`, `read_alternative`.

학교 필드: name, type, founding_type, district, hs_category(고등만), coedu(중·고만), total_classes, classes_by_grade, special_classes, total_students, students_by_grade, address, lat, lng, founded, zipcode, phone, fax, homepage, avg_students_per_class, avg_students_per_class_by_grade

`type`은 5종: `"초등학교"`, `"중학교"`, `"고등학교"`, `"특수학교"`, `"각종학교"`.

`classes_by_grade` / `students_by_grade`의 키:
- 초등: `"1"`~`"6"` (6단계)
- 중·고·각종학교: `"1"`~`"3"` (3단계)
- **특수학교**: `"유치원"`, `"초등"`, `"중"`, `"고"`, `"전공과"` (문자열 키!)

**UI 렌더링 주의**: 학년 라벨은 `gradeLabel()` 함수로 처리. 숫자 키는 `"1학년"`처럼 접미사, 문자 키는 그대로 표시. 학년 정렬은 `sortGrades()`로 커스텀 순서 적용 (특수학교는 유치원→초등→중→고→전공과 순).

이름 매칭: 직접 → "울산" 접두사 추가 → "울산" 제거 순으로 시도 (`find_match`, `matched_key` 헬퍼).

**중복 좌표 자동 오프셋**: 여러 학교가 같은 좌표를 갖는 경우 (예: 울산고운중·고는 같은 부지), JSON 생성 단계에서 학교명 가나다순 두 번째부터 약 16m(위도 0.00015) 간격으로 자동 오프셋. xlsx 원본은 손대지 않음.

**신규/폐교 감지**: `import_excel.py` 실행 시 현황 엑셀에 있지만 위치/연락처 엑셀에 없는 학교(신규), 반대의 경우(폐교/개명 의심)를 콘솔에 경고로 출력.

**새 학교 추가 워크플로우**: 사용자가 "초/중/고 현황 엑셀 업데이트했어"라고 하면 Claude가 감지 → 한 학교씩 정보 수집(설립일자/주소/좌표/연락처) → `scripts/add_school.py`로 위치·연락처 엑셀에 동시 추가 → `import_excel.py` 재실행 → 배포. 폐교 감지 시에는 `remove_school.py` 사용.

### 행정구역 경계
GitHub vuski/admdongkor (2025년 1월) → 울산 55개 행정동 추출 → shapely unary_union으로 5개 구/군 합침 → `data/ulsan_districts.json`

### 통학구역
초등학교통학구역.shp (전국 7123개) → pyshp+pyproj로 울산(SD_CD=31) 126개 필터링 + EPSG:5186→WGS84 변환 → `data/ulsan_school_zones.json`

## 주요 기능

### 검색/필터/정렬
- 학교명 텍스트 검색 (부분 매칭, 하이라이트)
- 유형 필터 6개 (전체/초등/중학/고등/특수/각종) — 헤더 버튼 + 모바일 칩
- 구/군 드롭다운 필터
- 정렬: 이름순, 학생수, 학급수, 학급당 학생수 (각 오름/내림)
- **특수·각종학교 노출 규칙**: `currentType === 'all'`이고 구/군 필터 없음이면 숨김. 구/군 선택 또는 "특수"/"각종" 버튼 직접 클릭 시 노출.
- **정렬 분기**: 이름순(`name`)은 특수·각종도 가나다순 섞어서 정렬. 그 외(학생수/학급수/학급당)는 초·중·고만 정렬하고 특수·각종은 하단에 이름순으로 고정.
- 빈 상태 안내 + 필터 초기화 버튼

### 지도
- 카카오맵 pill 형태 마커, 색상 구분:
  - 초등학교 녹색 #059669, 중학교 파란 #2563EB, 고등학교 주황 #EA580C
  - 특수학교 보라 #7C3AED, 각종학교 청록 #0891B2
- 줌 레벨별 3단계 마커 크기 (level ≤4: 약칭 표시, 5~7: 단일글자, 그 이상: 점)
- 구/군 필터 시 해당 행정구역 경계 폴리곤 오버레이
- 초등학교 선택 시 통학구역 폴리곤 표시 (녹색 실선, fillOpacity: 0.2)
- **같은 좌표의 두 학교는 import_excel.py 후처리에서 자동 16m 오프셋** (예: 울산고운중·고)

### 마커 약칭 규칙 (shortName 함수)
- **초/중/고**: "울산" 유지, 초등학교 접미사는 "초", 중학교는 "중", 고등학교는 "고"
  - 특수 변환: 여자상업→여상, 상업→상, 공업→공, 여자→여, 스포츠과학→스포츠
- **특수학교**: "울산" 접두사만 제거 (울산행복학교 → 행복학교, 메아리학교는 그대로)
- **각종학교**:
  - 중학교로 끝나면 "학교" 제거 (울산고운중학교 → 울산고운중)
  - 고등학교로 끝나면 "등학교" 제거 (울산고운고등학교 → 울산고운고)
  - 그 외는 "울산" 접두사 제거 (울산온라인학교 → 온라인학교)

### 사이드바 ↔ 지도 연동
- 카드 hover → 마커 강조, 마커 hover → 카드 강조
- **사이드바 클릭** → 지도 이동 + 마커 강조 + 통학구역 표시 (팝업 없음)
- **지도 마커 클릭** → 위와 동일 + 팝업 표시 (PC) / 바텀 시트 표시 (모바일)
- 팝업 닫아도 선택 상태 + 통학구역 유지
- 필터(유형/구/군) 변경 → 통학구역 + 선택 상태 초기화

### 학교 비교
- 카드 체크박스로 2~3개 선택 → 하단 비교 바 → 비교 모달 (테이블)
- 비교 항목: 학교명, 유형, 설립, 구/군, 공학, 고교유형, 학생수, 학급수, 학급당 학생수, 개교일, 주소

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
- `sortGrades(grades)` — 학년 키 정렬 (특수학교의 유치원→초→중→고→전공과 순, 숫자 키는 숫자 정렬)
- `gradeLabel(g)` — 학년 라벨 (숫자면 "N학년", 문자 키면 그대로)
- `openCompare()` / `closeCompare()` / `toggleCompare(id)` — 학교 비교

## 실행

```bash
python serve.py
# http://localhost:8080 접속
```

## 배포

Cloudflare Workers: `bash deploy.sh` 실행 (index.html·data/*.json을 deploy/로 복사 후 `wrangler deploy`).
- 필요: `CLOUDFLARE_API_TOKEN` 환경변수 (Windows 사용자 환경변수에 등록되어 있음)
- 배포 URL: https://ulsanschool.kr

# 모바일 바텀 시트 설계

## 문제

모바일(768px 이하)에서 지도 마커 클릭 시 Leaflet 팝업이 지도 영역(50vh)보다 커서 잘려 보임. PC에서는 화면이 넓어 문제 없음.

## 해결

모바일에서만 Leaflet 팝업 대신 바텀 시트로 학교 상세 정보를 표시한다. PC는 기존 팝업 그대로 유지.

## 적용 범위

- **모바일(768px 이하):** 바텀 시트
- **PC(769px 이상):** 기존 Leaflet 팝업 (변경 없음)

## 바텀 시트 구조

```
┌─────────────────────────┐
│      지도 영역 (40%)      │  ← 반투명 오버레이, 터치 시 시트 닫기
│   [마커] [마커] [마커]    │
├─── ──── ────────────────┤  ← border-radius:16px 16px 0 0
│        ─── (핸들)         │
│  [초등학교] 남구 · 공립  ✕ │  ← 고정 헤더 (스크롤 안 됨)
│  울산강남초등학교          │
├───────────────────────────┤
│  기본 정보              ↕ │  ← 스크롤 영역
│  설립: 공립               │
│  개교: 1990. 3. 1         │
│  주소: 울산 남구 ...       │
│  전화 / 팩스 / 웹         │
│                           │
│  학생/학급 현황            │
│  학년 | 학급 | 학생 | 평균 │
│  1학년 |  5  | 132 | 26.4 │
│  ...                      │
│  계   | 32  | 823 | 25.7 │
└───────────────────────────┘
```

## 동작

| 동작 | 결과 |
|------|------|
| 마커 클릭 | 바텀 시트 슬라이드업 (0.35s ease-out) + 오버레이 표시 |
| ✕ 버튼 클릭 | 바텀 시트 슬라이드다운 + 오버레이 제거 |
| 오버레이(지도) 터치 | 바텀 시트 닫기 |
| 시트 내부 스크롤 | 내용만 스크롤, 지도 안 움직임 |
| 다른 마커 클릭 | 시트 내용 교체 (닫고 다시 열 필요 없음) |
| 필터 변경 | 시트 닫기 |

## 구현 방식

### HTML
- `#bottomSheet` div를 `#map` 영역 아래(또는 `.main` 내)에 추가
- 구조: 핸들 → 고정 헤더(학교명+닫기) → 스크롤 영역(기본정보+테이블)

### CSS
- `.bottom-sheet`: `position:fixed; bottom:0; left:0; right:0; height:60vh; transform:translateY(100%); transition:transform 0.35s`
- `.bottom-sheet.open`: `transform:translateY(0)`
- `.sheet-overlay`: `position:fixed; inset:0; background:rgba(0,0,0,0.15)`
- 모두 `@media (max-width:768px)` 안에 배치
- PC에서는 `display:none`

### JS 변경

`selectSchool(id, openPopup)` 함수 수정:
- 모바일 감지: `window.innerWidth <= 768`
- 모바일이면: `openPopup` 무시, 대신 바텀 시트 열기. 시트 내용을 `createPopup(school)` 과 동일한 데이터로 채움.
- PC이면: 기존 로직 그대로 (`markers[id].openPopup()`)

팝업 내용 생성:
- 기존 `createPopup(s)` 함수의 HTML을 바텀 시트에도 재사용. 단, 시트 전용 레이아웃으로 별도 함수 `createSheetContent(s)` 생성하거나, 동일 HTML을 시트 스크롤 영역에 삽입.

닫기:
- ✕ 버튼 click → `closeBottomSheet()`
- 오버레이 click → `closeBottomSheet()`
- 필터/유형 변경 시 → `closeBottomSheet()` 호출 추가

### 터치 스크롤 격리
- 시트 스크롤 영역에 `overscroll-behavior: contain` 적용
- 시트가 열려 있을 때 지도의 터치 이벤트 차단 방지 (오버레이가 처리)

## 기존 코드 영향

- `selectSchool()`: 모바일 분기 추가
- `applyFilters()`: 바텀 시트 닫기 호출 추가
- `createPopup()`: 변경 없음 (PC용으로 유지)
- 마커 클릭 이벤트: 변경 없음 (selectSchool 내부에서 분기)
- deploy/index.html: 동일하게 반영

## 목업

인터랙티브 목업: `.superpowers/brainstorm/72306-1775245698/content/mobile-mockup.html`

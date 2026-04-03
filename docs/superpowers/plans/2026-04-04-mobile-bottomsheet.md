# 모바일 바텀 시트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 모바일(768px 이하)에서 마커 클릭 시 Leaflet 팝업 대신 고정 높이 바텀 시트로 학교 정보를 표시한다. PC는 변경 없음.

**Architecture:** `index.html` 단일 파일에 HTML/CSS/JS를 추가. 모바일 감지는 `window.innerWidth <= 768`로 판단. `selectSchool()` 함수 내부에서 모바일이면 팝업 대신 바텀 시트를 열고, PC면 기존 동작 유지. 완료 후 `deploy/index.html`에 동일 반영.

**Tech Stack:** 순수 HTML/CSS/JS (기존 스택 유지), CSS transition 애니메이션

---

### Task 1: 바텀 시트 HTML + CSS 추가

**Files:**
- Modify: `index.html:446` (HTML — `</div><!-- .main -->` 직전에 바텀 시트 삽입)
- Modify: `index.html:363-394` (CSS — `@media (max-width: 768px)` 블록 안에 스타일 추가)

- [ ] **Step 1: 바텀 시트 HTML 추가**

`index.html`의 `<button class="search-area-btn" ...>` (446행) 바로 아래, `</div><!-- .main 끝 -->` 직전에 삽입:

```html
<!-- 모바일 바텀 시트 -->
<div class="sheet-overlay" id="sheetOverlay"></div>
<div class="bottom-sheet" id="bottomSheet">
  <div class="sheet-handle"><div></div></div>
  <div class="sheet-header" id="sheetHeader"></div>
  <div class="sheet-scroll" id="sheetScroll"></div>
</div>
```

- [ ] **Step 2: 바텀 시트 CSS 추가**

`index.html`의 `@media (max-width: 768px)` 블록(363행) 끝 부분, `}` 닫는 중괄호 직전(391행 뒤)에 삽입:

```css
/* 바텀 시트 */
.sheet-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.15);
  z-index: 1000;
}
.sheet-overlay.open { display: block; }

.bottom-sheet {
  display: none;
  position: fixed;
  bottom: 0; left: 0; right: 0;
  height: 60vh;
  background: #fff;
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -4px 24px rgba(0,0,0,0.15);
  z-index: 1001;
  flex-direction: column;
  transform: translateY(100%);
  transition: transform 0.35s cubic-bezier(0.4,0,0.2,1);
}
.bottom-sheet.open {
  display: flex;
  transform: translateY(0);
}

.sheet-handle {
  display: flex;
  justify-content: center;
  padding: 10px 0 4px;
  flex-shrink: 0;
}
.sheet-handle div {
  width: 36px; height: 4px;
  background: #D1D5DB; border-radius: 2px;
}

.sheet-header {
  padding: 0 18px 12px;
  flex-shrink: 0;
}

.sheet-scroll {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  padding: 0 18px 20px;
  border-top: 1px solid #F3F4F6;
}
```

- [ ] **Step 3: PC에서 바텀 시트 숨기기**

`@media (min-width: 769px)` 블록(392행)에 추가:

```css
.bottom-sheet, .sheet-overlay { display: none !important; }
```

- [ ] **Step 4: 브라우저에서 확인**

Run: `python serve.py` → http://localhost:8080
Expected: PC에서는 바텀 시트가 보이지 않음. 개발자 도구에서 모바일 뷰(375px)로 전환해도 아직 시트는 `open` 클래스가 없으므로 보이지 않음. 기존 기능 정상 동작.

- [ ] **Step 5: 커밋**

```bash
git add index.html
git commit -m "feat: add bottom sheet HTML/CSS for mobile"
```

---

### Task 2: 바텀 시트 열기/닫기 JS 함수 + selectSchool 분기

**Files:**
- Modify: `index.html:861-886` (JS — `selectSchool` 함수)
- Modify: `index.html:888` (JS — `window._selectSchool`)
- Modify: `index.html:~858` (JS — 새 함수 `openBottomSheet`, `closeBottomSheet` 추가)

- [ ] **Step 1: isMobile 헬퍼 추가**

`index.html`의 `clearSchoolZone()` 함수(856-858행) 바로 아래에 추가:

```javascript
  // 모바일 판별
  function isMobile() { return window.innerWidth <= 768; }
```

- [ ] **Step 2: createSheetContent 함수 추가**

`isMobile()` 아래에 바텀 시트 내용 생성 함수를 추가. 기존 `createPopup(s)`의 데이터를 바텀 시트 레이아웃에 맞게 재구성:

```javascript
  // 바텀 시트 내용 생성
  function createSheetContent(s) {
    const bc = BADGE_STYLES[s.type] || '';

    let foundedStr = '';
    if (s.founded && s.founded.length === 8) {
      const y = s.founded.slice(0,4), m = s.founded.slice(4,6), d = s.founded.slice(6);
      foundedStr = `${y}. ${parseInt(m)}. ${parseInt(d)}`;
    }

    // 헤더
    const headerHtml = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">
            <span style="${bc};padding:2px 8px;border-radius:5px;font-size:10px;font-weight:600">${s.type}</span>
            <span style="font-size:11px;color:#9CA3AF">${s.district}${s.founding_type ? ' · '+s.founding_type : ''}</span>
          </div>
          <div style="font-size:17px;font-weight:700;color:#111827;letter-spacing:-0.3px">${s.name}</div>
        </div>
        <button onclick="window._closeBottomSheet()" style="width:28px;height:28px;border-radius:50%;background:#F3F4F6;border:none;display:flex;align-items:center;justify-content:center;font-size:14px;color:#6B7280;cursor:pointer;flex-shrink:0;margin-top:2px">✕</button>
      </div>`;

    // 기본 정보
    const infoRow = (label, value) => value ? `
      <div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #F3F4F6">
        <span style="color:#9CA3AF;font-size:11px">${label}</span>
        <span style="color:#374151;font-size:11px;font-weight:500;text-align:right;max-width:200px">${value}</span>
      </div>` : '';

    let infoHtml = `
      <div style="font-size:10px;font-weight:600;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.5px;margin:14px 0 6px">기본 정보</div>
      ${infoRow('공학', s.coedu)}
      ${infoRow('고교유형', s.hs_category)}
      ${infoRow('개교', foundedStr)}`;

    if (s.address) {
      infoHtml += `
      <div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #F3F4F6">
        <span style="color:#9CA3AF;font-size:11px;flex-shrink:0">주소</span>
        <span style="color:#374151;font-size:11px;font-weight:500;text-align:right;max-width:200px">${s.address}${s.zipcode ? ' ('+s.zipcode.trim()+')' : ''}</span>
      </div>`;
    }
    infoHtml += infoRow('전화', s.phone);
    infoHtml += infoRow('팩스', s.fax);
    if (s.homepage) {
      infoHtml += `
      <div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #F3F4F6">
        <span style="color:#9CA3AF;font-size:11px">웹</span>
        <a href="${s.homepage}" target="_blank" style="color:#2563EB;text-decoration:none;font-size:11px;font-weight:500">${s.homepage.replace(/^https?:\/\//, '').replace(/\/$/, '')}</a>
      </div>`;
    }

    // 학년별 테이블
    let tableHtml = '';
    if (s.classes_by_grade && s.students_by_grade) {
      const grades = Object.keys(s.classes_by_grade).sort();
      const totalCls = grades.reduce((a, g) => a + (s.classes_by_grade[g]||0), 0);
      const totalStu = grades.reduce((a, g) => a + (s.students_by_grade[g]||0), 0);
      const rows = grades.map(g => {
        const c = s.classes_by_grade[g]||0;
        const st = s.students_by_grade[g]||0;
        const av = s.avg_students_per_class_by_grade ? (s.avg_students_per_class_by_grade[g]||0) : 0;
        return `<tr>
          <td style="padding:5px 6px;border-bottom:1px solid #F3F4F6;color:#374151">${g}학년</td>
          <td style="padding:5px 6px;border-bottom:1px solid #F3F4F6;text-align:right">${c}</td>
          <td style="padding:5px 6px;border-bottom:1px solid #F3F4F6;text-align:right">${st.toLocaleString()}</td>
          <td style="padding:5px 6px;border-bottom:1px solid #F3F4F6;text-align:right">${av}</td>
        </tr>`;
      }).join('');

      tableHtml = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:14px">
          <span style="font-size:10px;font-weight:600;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.5px">학생/학급 현황</span>
          <span style="font-size:9px;color:#D1D5DB">2026년 2월 기준</span>
        </div>
        <table style="width:100%;font-size:11px;border-collapse:collapse;margin-top:6px">
          <tr style="font-weight:600;color:#9CA3AF;font-size:10px">
            <td style="padding:5px 6px;border-bottom:1px solid #E5E7EB">학년</td>
            <td style="padding:5px 6px;border-bottom:1px solid #E5E7EB;text-align:right">학급</td>
            <td style="padding:5px 6px;border-bottom:1px solid #E5E7EB;text-align:right">학생</td>
            <td style="padding:5px 6px;border-bottom:1px solid #E5E7EB;text-align:right">평균</td>
          </tr>
          ${rows}
          <tr style="font-weight:700;color:#111827">
            <td style="padding:6px 6px">계</td>
            <td style="padding:6px 6px;text-align:right">${totalCls}</td>
            <td style="padding:6px 6px;text-align:right">${totalStu.toLocaleString()}</td>
            <td style="padding:6px 6px;text-align:right;color:#2563EB">${s.avg_students_per_class||0}</td>
          </tr>
        </table>`;
    }

    return { headerHtml, scrollHtml: infoHtml + tableHtml };
  }
```

- [ ] **Step 3: openBottomSheet / closeBottomSheet 함수 추가**

`createSheetContent` 아래에 추가:

```javascript
  // 바텀 시트 열기/닫기
  function openBottomSheet(school) {
    const { headerHtml, scrollHtml } = createSheetContent(school);
    document.getElementById('sheetHeader').innerHTML = headerHtml;
    document.getElementById('sheetScroll').innerHTML = scrollHtml;

    const sheet = document.getElementById('bottomSheet');
    const overlay = document.getElementById('sheetOverlay');
    overlay.classList.add('open');
    sheet.classList.add('open');
  }

  function closeBottomSheet() {
    document.getElementById('bottomSheet').classList.remove('open');
    document.getElementById('sheetOverlay').classList.remove('open');
  }
  window._closeBottomSheet = closeBottomSheet;
```

- [ ] **Step 4: 오버레이 클릭 시 닫기 이벤트**

`closeBottomSheet` 아래에 추가:

```javascript
  document.getElementById('sheetOverlay').addEventListener('click', closeBottomSheet);
```

- [ ] **Step 5: selectSchool 함수에 모바일 분기 추가**

기존 `selectSchool` 함수(861행)에서 `if (openPopup) markers[id].openPopup();` (877행)을 다음으로 교체:

변경 전:
```javascript
    if (openPopup) markers[id].openPopup();
```

변경 후:
```javascript
    if (openPopup) {
      if (isMobile()) {
        openBottomSheet(school);
      } else {
        markers[id].openPopup();
      }
    }
```

- [ ] **Step 6: 사이드바 클릭(\_selectSchool)에도 모바일 분기 추가**

기존(888행):
```javascript
  window._selectSchool = function(id) { selectSchool(id, false); };
```

변경 후:
```javascript
  window._selectSchool = function(id) {
    selectSchool(id, false);
    if (isMobile()) {
      const school = allSchools.find(s => s.id === id);
      if (school) openBottomSheet(school);
    }
  };
```

- [ ] **Step 7: 브라우저에서 동작 확인**

Run: http://localhost:8080 → 개발자 도구 모바일 뷰(375px)
- 마커 클릭 → 바텀 시트 슬라이드업, 팝업 안 뜸
- ✕ 버튼 클릭 → 시트 닫힘
- 오버레이 클릭 → 시트 닫힘
- PC 뷰(>768px) → 기존 팝업 정상 동작

- [ ] **Step 8: 커밋**

```bash
git add index.html
git commit -m "feat: open bottom sheet on mobile marker click"
```

---

### Task 3: 필터/상태 변경 시 바텀 시트 닫기

**Files:**
- Modify: `index.html:590` (JS — `applyFilters` 함수)

- [ ] **Step 1: applyFilters에 closeBottomSheet 호출 추가**

`applyFilters` 함수(590행) 첫 줄에 추가:

변경 전:
```javascript
  function applyFilters(skipFitBounds) {
    filteredSchools = allSchools.filter(s => {
```

변경 후:
```javascript
  function applyFilters(skipFitBounds) {
    closeBottomSheet();
    filteredSchools = allSchools.filter(s => {
```

- [ ] **Step 2: 확인**

모바일 뷰에서 바텀 시트 열린 상태 → 유형 필터 변경 → 시트 닫힘 확인.

- [ ] **Step 3: 커밋**

```bash
git add index.html
git commit -m "feat: close bottom sheet on filter change"
```

---

### Task 4: 바텀 시트 열릴 때 display 트랜지션 처리

**Files:**
- Modify: `index.html` (CSS — `.bottom-sheet` 스타일)

바텀 시트는 `display:none` → `display:flex` 전환 시 CSS transition이 동작하지 않는 문제가 있다. `open` 클래스 추가 시 display를 먼저 바꾸고 한 프레임 뒤에 transform을 적용해야 한다.

- [ ] **Step 1: CSS 수정 — display를 flex로 변경하고 visibility로 숨기기**

기존 CSS:
```css
.bottom-sheet {
  display: none;
  ...
  transform: translateY(100%);
  transition: transform 0.35s cubic-bezier(0.4,0,0.2,1);
}
.bottom-sheet.open {
  display: flex;
  transform: translateY(0);
}
```

변경 후:
```css
.bottom-sheet {
  display: flex;
  position: fixed;
  bottom: 0; left: 0; right: 0;
  height: 60vh;
  background: #fff;
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -4px 24px rgba(0,0,0,0.15);
  z-index: 1001;
  flex-direction: column;
  transform: translateY(100%);
  transition: transform 0.35s cubic-bezier(0.4,0,0.2,1);
  pointer-events: none;
}
.bottom-sheet.open {
  transform: translateY(0);
  pointer-events: auto;
}
```

이렇게 하면 항상 `display:flex`이되 `transform:translateY(100%)`로 화면 밖에 위치하고, `pointer-events:none`으로 터치 이벤트도 차단. `open` 시 슬라이드업 + 터치 활성화.

- [ ] **Step 2: 오버레이도 동일하게 변경**

기존:
```css
.sheet-overlay {
  display: none;
  ...
}
.sheet-overlay.open { display: block; }
```

변경 후:
```css
.sheet-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.15);
  z-index: 1000;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s;
}
.sheet-overlay.open {
  opacity: 1;
  pointer-events: auto;
}
```

- [ ] **Step 3: 확인**

모바일 뷰에서 마커 클릭 → 바텀 시트가 부드럽게 슬라이드업 되는지 확인. 닫을 때도 슬라이드다운 애니메이션 동작 확인.

- [ ] **Step 4: 커밋**

```bash
git add index.html
git commit -m "fix: use transform+pointer-events for smooth sheet animation"
```

---

### Task 5: deploy/index.html 동기화

**Files:**
- Modify: `deploy/index.html` — index.html의 모든 변경사항을 동일하게 반영

- [ ] **Step 1: deploy/index.html에 전체 변경사항 복사**

`index.html`을 `deploy/index.html`에 복사:

```bash
cp index.html deploy/index.html
```

(두 파일은 동일해야 하므로 직접 복사가 가장 안전하다.)

- [ ] **Step 2: 확인**

```bash
diff index.html deploy/index.html
```

Expected: 차이 없음.

- [ ] **Step 3: 커밋**

```bash
git add deploy/index.html
git commit -m "chore: sync deploy/index.html with bottom sheet changes"
```

---

### Task 6: 최종 검증

- [ ] **Step 1: PC 뷰 검증**

http://localhost:8080 → 브라우저 전체 화면:
- 마커 클릭 → 기존 Leaflet 팝업 정상 표시
- 사이드바 클릭 → 지도 이동 + 마커 강조 (팝업 없음)
- 필터/검색/정렬 모두 정상

- [ ] **Step 2: 모바일 뷰 검증**

개발자 도구 → 모바일 뷰(375px):
- 마커 클릭 → 바텀 시트 슬라이드업 (Leaflet 팝업 안 뜸)
- ✕ 버튼 → 시트 닫힘
- 오버레이 클릭 → 시트 닫힘
- 다른 마커 클릭 → 시트 내용 교체
- 사이드바 카드 클릭 → 바텀 시트 열림
- 필터 변경 → 시트 닫힘
- 시트 내부 스크롤 → 지도 안 움직임
- 학년별 테이블까지 전부 스크롤 가능

- [ ] **Step 3: 최종 커밋 (필요시)**

모든 테스트 통과하면 완료.

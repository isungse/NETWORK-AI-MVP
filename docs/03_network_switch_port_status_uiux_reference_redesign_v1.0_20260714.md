# NMS 스위치 포트 전면 패널 UI/UX 리디자인 Codex 실행 프롬프트

## Goal

현재 Network AI MVP의 `/operations` 화면에 있는 `Port Matrix View`를 샘플 HPE 스위치 Web UI의 장비 전면 패널 형태를 참고하여 리디자인한다.

이번 작업의 목적은 샘플 화면을 그대로 복제하는 것이 아니라 다음 사용자 가치를 현재 NMS 구조 안에서 구현하는 것이다.

1. 포트의 번호와 논리적 배치를 즉시 파악할 수 있어야 한다.
2. 링크 상태, 관리자 비활성 상태, 장애 상태, 선택 상태를 혼동 없이 구분해야 한다.
3. 기존 포트 조회, 필터, 상세 패널, 테이블 기능을 유지해야 한다.
4. 관측 시각과 데이터 출처를 계속 표시하여 참조 스냅샷을 실시간 상태로 오인하지 않게 해야 한다.

일반적인 최신 SaaS KPI 대시보드로 다시 설계하지 않는다. 스위치 전면부처럼 낮고 긴 섀시, 2단 포트 배열, 작은 상태 표시, 절제된 범례가 핵심 시각 언어다.

---

## 정확한 작업 범위

리디자인 대상은 `src/network_ai_mvp/static/operations.html`의 기존 `Port Matrix View` 영역이다.

다음 공통 영역은 유지한다.

- 글로벌 헤더와 좌측 사이드바
- 선택 장비 요약
- Operations Dashboard와 토폴로지
- Inventory와 검색
- 우측 Detail Panel
- Diagnostic Result, CHECK, Neighbors, Audit 영역
- 기존 API 경로와 응답 형식

Port Matrix 영역에서는 다음 기능을 유지한다.

- 장비 선택에 따른 포트 데이터 로딩
- Status, Mode, VLAN, Description/Port 필터
- 포트 선택과 우측 상세 패널 연동
- 상세 분석용 Table view
- 수동 Refresh
- 최신 관측 시각, 수집 목적, 최신 스냅샷 여부 표시

기존 KPI 카드 형태의 포트 요약은 전면 패널 위나 아래의 compact summary line으로 단순화할 수 있다. 큰 카드 묶음은 만들지 않는다.

---

## 작업 전 필수 확인

구현 전에 다음 문서를 읽는다.

- `AGENTS.md`
- `.codex/rules/meta.md`
- `.codex/rules/architecture.md`
- `.codex/rules/workflow.md`
- `README.md`
- `PROJECT_STATUS.md`
- `src/network_ai_mvp/static/operations.html`
- `src/network_ai_mvp/static/app.js`
- `src/network_ai_mvp/static/styles.css`
- `src/network_ai_mvp/models.py`
- `src/network_ai_mvp/parsers.py`
- `src/network_ai_mvp/services/collection.py`

현재 확인된 프론트엔드 구조는 React나 TypeScript가 아니라 순수 HTML, CSS, JavaScript다.

따라서 다음을 지킨다.

- JSX 또는 TypeScript를 새로 도입하지 않는다.
- npm 기반 빌드 시스템을 새로 추가하지 않는다.
- 기존 DOM 렌더링 패턴과 null-safe 노드 접근 방식을 따른다.
- `app.js`는 `/`와 `/operations`에서 함께 사용되므로 새 UI가 Operations 화면에만 적용되게 한다.
- 관련 없는 `app.js` 기능을 광범위하게 리팩터링하지 않는다.

---

## 참조 이미지 확인

참조 이미지는 다음 우선순위로 찾는다.

1. 저장소의 `docs/references/HP_WEBUI.png`
2. 현재 작업에 첨부된 `HP_WEBUI.png`
3. 현재 워크스테이션의 `D:/03. AI 학습/HP_WEBUI.png`

하나라도 읽을 수 있으면 해당 이미지를 사용한다. 저장소 경로가 없다는 이유만으로 중단하지 않는다.

세 경로 모두 사용할 수 없으면 임의로 시각 디자인을 추정하지 말고 참조 이미지를 찾을 수 없다고 보고한다. 외부 경로의 이미지를 자동으로 복사하거나 Git에 추가하지 않는다.

참조 이미지는 약 597 × 288 크기의 레거시 HPE 관리 UI이며 다음 특징을 가진다.

- 상단 왼쪽의 낮고 긴 짙은 회색 섀시
- 검은 RJ45 포트 외형
- 홀수 포트가 위, 짝수 포트가 아래인 2단 배열
- 1~8, 9~16, 17~24 포트 뱅크 사이의 넓은 간격
- 25~28 추가 포트의 별도 단일 행
- 섀시 오른쪽의 작은 장비 모델명
- 포트 전체보다 포트 번호 또는 내부 인디케이터 중심의 상태색
- 우측 정렬된 compact Refresh 컨트롤
- 얇은 구분선과 작은 상태 범례
- 흰 배경과 충분한 여백

이미지는 시각적 모티프다. 현재 NMS의 글로벌 레이아웃, 접근성, 데이터 안전 표시를 제거하면서까지 픽셀 단위로 복제하지 않는다.

---

## 현재 데이터 계약과 제한

현재 `PortObservation`에서 사용할 수 있는 주요 필드는 다음과 같다.

```text
interface
status
vlan
duplex
speed
speed_mbps
description
endpoint_ips
endpoint_macs
neighbor_name
neighbor_ip
neighbor_platform
fcs_errors
align_errors
symbol_errors
rx_errors
runts
giants
tx_errors
source_timestamp
source_purpose
```

현재 데이터에는 다음 정보가 보장되지 않는다.

- 실제 전면 패널 좌표
- RJ45, SFP, SFP+ 같은 물리 포트 타입
- PoE 지원 또는 공급 상태
- 모듈 슬롯의 실제 폭과 위치
- POST 실패 또는 미인식 모듈 상태

없는 정보를 UI에서 추정하거나 하드코딩하지 않는다. PoE와 포트 타입은 실제 응답 필드가 있을 때만 표시한다.

장비 표시에는 현재 공개 API 필드만 사용한다.

```text
hostname → platform → device_id
```

권장 표시는 `hostname`을 기본으로 하고, 공간이 허용되면 `vendor`와 `platform`을 작은 보조 텍스트로 추가하는 방식이다.

---

## 포트 배열 결정 규칙

### 1. HPE 24+4 참조 레이아웃

다음 조건을 만족하는 명시적 테스트 데이터 또는 확인된 장비에만 샘플의 24+4 배열을 적용한다.

```text
상단: 1  3  5  7   9  11  13  15   17  19  21  23
하단: 2  4  6  8   10 12  14  16   18  20  22  24
추가: 25 26 27 28
```

장비 모델이나 레이아웃 메타데이터가 이를 보장하지 않으면 모든 장비를 24+4로 강제하지 않는다.

### 2. 48포트 및 48+업링크 레이아웃

48개의 물리 액세스 포트가 확인된 장비는 다음 기본 배열을 사용한다.

```text
상단: 1  3  5  7  9  11 | 13 15 17 19 21 23 | 25 27 29 31 33 35 | 37 39 41 43 45 47
하단: 2  4  6  8  10 12 | 14 16 18 20 22 24 | 26 28 30 32 34 36 | 38 40 42 44 46 48
```

기본 logical fallback은 12개 번호 단위의 네 개 포트 뱅크로 구분한다. 실제 장비 모델 또는 레이아웃 메타데이터가 8개 단위나 다른 모듈 구성을 제공하면 실제 메타데이터를 우선한다.

48포트 장비에 추가 물리 포트가 확인되면 다음 규칙을 적용한다.

- 49~52가 실제 물리 인터페이스로 확인되면 기본 48포트 뱅크 오른쪽의 별도 additional/uplink group에 배치한다.
- 메타데이터가 단일 행을 명시하면 `49 50 51 52` 단일 행으로 표시한다.
- 메타데이터가 2×2 배치를 명시하면 상단 `49 51`, 하단 `50 52`로 표시한다.
- 포트 타입 필드가 없으면 49~52를 SFP/SFP+라고 단정하지 않고 `Additional ports`로 표시한다.
- 49~52 데이터가 없으면 빈 업링크 포트를 임의로 생성하지 않는다.
- 53 이상의 물리 포트가 존재하면 숨기거나 자르지 않고 모델 메타데이터 또는 일반 fallback 규칙으로 계속 표시한다.

다음 인터페이스는 48개 물리 포트 수 계산에서 제외한다.

- `Po`, `Port-channel` 같은 집계 논리 인터페이스
- VLAN, Loopback, CPU 인터페이스
- 별도 관리 포트로 명확하게 식별된 Management 인터페이스

단, 현재 데이터에 물리 포트 타입이나 관리 포트 식별 정보가 없으면 이름만 보고 무리하게 제외하지 않는다. 확실하지 않은 인터페이스는 별도 `Unclassified interfaces` 영역에 표시하고 실제 전면 패널 포트라고 주장하지 않는다.

48포트 전면 패널도 필터 적용 시 포트 슬롯을 제거하거나 재배치하지 않는다. 화면 폭이 부족하면 포트 크기를 과도하게 줄이지 말고 섀시 내부 수평 스크롤을 사용한다.

### 3. 일반 장비 fallback

실제 물리 좌표가 없을 때는 `logical faceplate`로 표시한다.

- `Et`, `Ethernet`, `Gi`, `GigabitEthernet`, `Te`, `TenGigabitEthernet`, `Fa`, `FastEthernet` 계열을 물리 포트 후보로 사용한다.
- 기존 natural interface sort 순서를 유지한다.
- 슬롯/모듈 번호가 있는 인터페이스는 슬롯별로 그룹화한다.
- 각 그룹 안에서는 홀수/짝수 상하 관계를 가능한 범위에서 유지한다.
- `Po`, `Port-channel`, VLAN, Loopback 같은 논리 인터페이스는 물리 패널에 섞지 않고 별도의 compact logical interfaces 영역이나 기존 Table view에서 표시한다.
- 실제 배치임을 보장할 수 없으면 `Logical port order · physical slot metadata unavailable` 안내를 표시한다.

포트 수가 많아도 임의로 24개만 자르지 않는다. 수평 스크롤과 포트 뱅크 분할을 사용한다.

### 4. 필터 적용 규칙

전면 패널에서 필터에 맞지 않는 포트를 DOM에서 제거하거나 다시 정렬하지 않는다. 그렇게 하면 물리적 위치가 무너진다.

- 전체 포트 슬롯의 위치를 유지한다.
- 필터에 맞지 않는 포트는 흐리게 표시한다.
- 필터에 맞는 포트는 정상 명도 또는 강조 테두리로 표시한다.
- Table view에서는 기존처럼 일치하는 행만 표시해도 된다.
- 빈 슬롯 또는 데이터가 없는 번호를 임의로 생성하지 않는다.

---

## 스위치 전면 패널 시각 규칙

### 섀시

- 짙은 회색 배경
- 얇은 회색 외곽선
- 그림자 없음
- 라운드 처리 최소화
- 낮고 긴 직사각형
- 화면 전체 폭을 강제로 채우지 않음
- 포트 뱅크는 왼쪽, 장비명은 오른쪽
- 장비명이 포트와 겹치지 않도록 최소 폭과 여백 확보

권장 CSS 변수:

```css
--switch-chassis-bg: #55555a;
--switch-chassis-border: #77777c;
--switch-port-bg: #0b0b0c;
--switch-port-border: #9a9a9d;
--switch-port-text: #d8d8d8;
--port-status-unconnected: #f0f0f0;
--port-status-connected: #98df70;
--port-status-admin-disabled: #8e6868;
--port-status-fault: #b64d3e;
--port-status-unknown: #8b8d91;
--port-selection: #5869d8;
```

기존 디자인 토큰과 충돌하면 기존 토큰을 우선하고 새 변수는 switch panel 범위에 한정한다.

### 포트 외형

- 검은색 또는 매우 어두운 내부
- 회색 이중 외곽선 또는 inset border
- CSS pseudo-element나 inline SVG로 작은 RJ45 홈 표현
- 중앙 또는 하단에 작은 포트 번호
- 상태색은 포트 전체를 크게 채우기보다 포트 번호 또는 내부 LED/인디케이터에 적용
- 카드형 둥근 타일, 네온, glow, 그라데이션, 애니메이션 금지
- 개별 포트 PNG 반복 사용 금지

---

## 포트 상태 표현

운영 상태, 진단 심각도, 선택 상태를 하나의 색상으로 합치지 않는다.

### 1. 운영 상태

```text
connected              → connected, 녹색 번호/LED
notconnect 또는 down   → unconnected, 흰색/밝은 회색 번호/LED
disabled               → admin-disabled, 탁한 갈색 번호/LED
errdisabled            → fault, 붉은색 번호/LED
null 또는 미지원 값    → unknown, 중립 회색 번호/LED
```

`errdisabled`는 POST 실패와 동일한 의미가 아니다. 화면과 범례에는 실제 상태명 또는 `Port fault / errdisabled`로 표시한다.

POST 실패나 미인식 모듈은 API가 해당 상태를 명시적으로 제공할 때만 별도 상태로 추가한다.

### 2. 진단 심각도

CRC/FCS, Rx, Runts, Giants, Tx 오류가 있는 연결 포트는 연결 상태를 잃지 않게 한다.

- 운영 상태 LED는 녹색을 유지할 수 있다.
- 별도의 작은 경고 점, 배지 또는 얇은 붉은 테두리로 진단 이상을 표시한다.
- 오류 카운터가 0보다 크다는 이유만으로 포트를 `down`이나 `errdisabled`처럼 표현하지 않는다.

### 3. 선택 상태

선택은 API 상태가 아니라 UI 상태다.

- 파란색 외곽선 또는 focus ring 사용
- 기존 상태 LED 색상을 덮어쓰지 않음
- `aria-pressed="true"` 또는 적절한 선택 속성 사용
- 키보드 포커스와 마우스 선택이 동일하게 인식되게 함

### 범례

범례는 실제로 표시 가능한 상태만 렌더링한다.

```text
미연결
연결됨
관리자 비활성
포트 장애 / errdisabled
상태 미확인
선택됨 — 상태가 아니라 UI 선택 표시
진단 경고 — 오류 카운터 존재
```

HPE 고유 `Bn`, `Rn` 설명은 기본으로 표시하지 않는다. 실제 데이터에 Port-channel 또는 LACP 정보가 있으면 프로젝트 용어인 `Po`, `Port-channel`, LACP로 설명한다.

---

## 상세 정보와 접근성

각 물리 포트는 가능하면 `<button type="button">`으로 렌더링한다.

필수 사항:

- 포트 번호를 화면에 항상 표시
- 상태 약어 또는 아이콘을 함께 제공하여 색상만으로 구분하지 않음
- `aria-label`에 interface, status, speed, duplex, VLAN, description 포함
- 선택 포트에 `aria-pressed` 적용
- `:focus-visible` 스타일 제공
- hover뿐 아니라 focus에서도 동일한 상세 정보 접근 가능
- tooltip은 보조 수단으로만 사용
- 포트 클릭 시 기존 `renderPortDetail` 흐름과 우측 Detail Panel 연동 유지
- 진단 버튼과 수집 버튼 동작을 변경하지 않음

PoE 정보는 실제 필드가 없으면 tooltip과 ARIA 문구에서도 생략한다.

---

## 관측 시각과 데이터 안전 표시

샘플 이미지에 없더라도 현재 NMS의 다음 정보는 제거하지 않는다.

- `timestamp`
- `purpose`
- `is_latest_observation`
- `latest_timestamp`
- `latest_purpose`
- API의 `message`

다음 원칙을 지킨다.

- 참조 스냅샷을 실시간 데이터라고 표현하지 않는다.
- 최신 관측이 포트 데이터가 아니면 기존 안내 문구를 유지한다.
- stale 또는 reference 상태는 compact metadata line으로 표시한다.
- 자동 Refresh는 저장된 최신 관측을 다시 조회하는 것이며 장비에 live collection을 실행하는 기능이 아님을 표시한다.

---

## Refresh Period

이번 리디자인에서는 기존 포트 조회 API를 이용한 프론트엔드 자동 새로고침을 허용한다. 이는 이번 작업에서 허용되는 유일한 신규 동작이다.

구성:

```text
Refresh Period [Off | 15 seconds | 30 seconds | 60 seconds] [Refresh]
```

규칙:

- 기본값은 30초
- 현재 선택 장비의 `/devices/{device_id}/ports/latest`만 GET으로 다시 조회
- 기존 `loadPorts` 흐름과 `selectionRequestId` 보호 로직 재사용
- topology SSE 또는 `/monitoring/latest` polling 타이머를 재사용하지 않음
- 자동 Refresh가 collection, CHECK 또는 장비 CLI 실행을 호출하지 않음
- 수동 Refresh와 자동 Refresh의 중복 요청 방지
- 조회 중 Refresh 버튼과 select에 적절한 busy 상태 표시
- 장비 선택이 바뀌면 이전 장비 타이머/요청 정리
- `pagehide` 또는 화면 종료 시 타이머 정리
- 문서가 hidden 상태이면 polling 일시 중지하고 복귀 시 한 번 갱신
- 오래된 응답이 새 장비 선택 결과를 덮어쓰지 않게 함
- 오류는 기존 상태 표시 체계를 사용하고 마지막 정상 포트 배열은 유지

안전하게 구현하기 어려운 경우 기능이 없는 select를 만들지 않는다. 수동 Refresh만 유지하고 자동 Refresh를 제외한 이유를 완료 보고에 기록한다.

---

## 전체 Port Matrix 영역 순서

```text
1. 패널 제목과 최신 관측 metadata
2. 스위치 전면 패널
3. compact port summary
4. 우측 정렬 Refresh Period 컨트롤
5. 얇은 구분선
6. compact 상태 범례
7. 기존 필터
8. 기존 상세 Table view
```

샘플의 여백을 참고하되 현재 Operations 화면 안에서 불필요한 50px 이상의 빈 공간을 강제하지 않는다. 전면 패널과 Refresh 영역 사이에는 구조를 인식할 수 있는 여백만 둔다.

사용하지 않는 요소:

- 새로운 대형 페이지 제목
- 원형 차트와 막대그래프
- 장식용 아이콘
- 강한 그림자
- 유리 효과
- 그라데이션
- 과도한 라운드 카드
- 포트 주변 애니메이션

---

## 반응형 처리

포트의 상대적 배열 보존이 우선이다.

- 데스크톱에서는 가로 전면 패널 유지
- 폭이 부족하면 섀시 내부 수평 스크롤 허용
- 홀수/짝수 상하 관계를 임의로 뒤집지 않음
- 포트 순서를 여러 줄 카드로 재배치하지 않음
- 포트 크기를 판독 불가능한 수준으로 축소하지 않음
- 장비명과 포트가 겹치지 않음
- 모바일 카드 UI로 변환하지 않음
- 긴 장비명은 말줄임표와 `title` 또는 접근 가능한 전체 이름 제공

---

## 코드 구조와 중복 방지

현재 저장소에 맞는 권장 함수 경계:

```text
renderSwitchFrontPanel
buildPhysicalPortGroups
normalizePortOperationalStatus
portHealthSeverity
renderPortStatusLegend
renderRefreshControls
buildPortAriaLabel
```

기본적으로 기존 `app.js`와 `styles.css` 안에 명확한 섹션으로 추가한다.

새 파일 분리가 실제 중복과 복잡도를 줄이는 경우에만 다음과 같은 정적 파일을 고려한다.

```text
src/network_ai_mvp/static/switch-panel.js
src/network_ai_mvp/static/switch-panel.css
```

새 파일을 만들면 다음을 함께 확인한다.

- `operations.html` 로드 순서
- `/` 화면에 미치는 영향
- 정적 자산 cache-busting 버전
- `pyproject.toml`의 기존 `static/*.js`, `static/*.css` 패키징 범위

포트 목록과 포트 상태를 HTML에 하드코딩하지 않는다. 동일한 색상이나 상태 매핑을 여러 함수와 CSS 위치에 중복 선언하지 않는다.

---

## 시각적 검증

브라우저 검증 시 기준 뷰포트는 우선 `1440 × 900`, 브라우저 확대 100%로 한다.

검증 대상:

- Operations 글로벌 레이아웃 유지
- 스위치 섀시 높이와 비율
- 포트 크기와 번호 정렬
- 포트 뱅크 간 간격
- HPE 24+4 fixture의 홀수/짝수 배열과 25~28 위치
- 48포트 fixture의 1~48 홀수/짝수 배열과 네 개 포트 뱅크
- 48+4 fixture에서 49~52 additional/uplink group의 분리와 위치
- 일반 Cisco/Arista 장비의 동적 포트 수 처리
- 장비명 오른쪽 정렬과 말줄임
- 선택, 운영 상태, 진단 경고의 독립적 표현
- Refresh 컨트롤 위치
- 범례와 필터 위치
- 수평 스크롤 시 포트 순서 유지
- 텍스트 또는 포트 겹침 없음

샘플과 같은 24+4 fixture에서는 포트 크기와 간격 차이를 약 4px 이내로 목표로 할 수 있다. 전체 Operations 화면이나 다른 포트 수의 장비에 4px 픽셀 일치를 강제하지 않는다.

가능하면 참조 이미지와 구현 결과의 component crop 스크린샷을 함께 비교한다.

---

## 기능 검증

다음 사용자 흐름을 확인한다.

1. `/operations` 로드
2. 장비 선택
3. 포트 데이터와 freshness metadata 표시
4. 포트 선택 후 우측 Detail Panel 갱신
5. Status, Mode, VLAN, 검색 필터 동작
6. 필터 후에도 전면 패널의 포트 위치 유지
7. Table view 필터 결과 유지
8. 수동 Refresh
9. 30초 자동 Refresh와 Off 전환
10. 장비 변경 시 이전 타이머와 오래된 응답 정리
11. 브라우저 콘솔 오류 없음

UI 검증 중 collection, CHECK, 진단 실행 버튼을 눌러 실제 장비 세션을 열지 않는다.

현재 저장소의 최소 검증 명령:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
node --check src\network_ai_mvp\static\app.js
node --check src\network_ai_mvp\static\monitoring.js
git diff --check
```

새 JavaScript 파일을 만들면 해당 파일에도 `node --check`를 실행한다.

현재 저장소에 구성되지 않은 TypeScript, npm lint, npm build 명령을 임의로 요구하거나 도입하지 않는다. 실제 설정 파일이 있을 때만 해당 검사를 추가한다.

---

## 변경 금지 범위

다음은 변경하지 않는다.

- 백엔드 API와 응답 스키마
- 데이터베이스 또는 JSON/JSONL 저장 구조
- 네트워크 장비 통신 방식
- Telnet, SSH, SNMP, CLI 처리 로직
- 수집 명령 allowlist
- 인증과 권한 로직
- 장비 등록 및 삭제 로직
- 라우팅 구조
- 프로젝트 전체 디자인 시스템
- Port Matrix 이외 페이지와 기능
- 실제 장비 상태를 변경하는 명령

필요한 최소 범위의 정적 프론트엔드와 관련 테스트만 변경한다.

---

## 완료 보고

작업 완료 후 한국어로 다음 내용을 보고한다.

1. 참조 이미지에서 적용한 시각적 특징
2. 변경한 파일 목록
3. HPE 24+4, 48포트, 48+업링크와 일반 장비 fallback 배열 방식
4. 물리 포트와 논리 인터페이스 분리 방식
5. 운영 상태, 진단 심각도, 선택 상태 매핑
6. 기존 필터, Table view, Detail Panel 보존 방식
7. 수동 및 자동 Refresh 구현과 타이머 정리 방식
8. freshness와 reference snapshot 표시 방식
9. 반응형과 접근성 처리
10. 실행한 테스트와 브라우저 검증 결과
11. 참조 이미지와 구현 결과 사이에 남은 차이
12. 실제 물리 배치를 위해 추가로 필요한 장비 메타데이터

중대한 차단 문제가 없으면 분석만 하고 멈추지 말고 구현, 검증, 완료 보고까지 진행한다. 차단 문제가 있으면 임의로 물리 정보나 상태를 추정하지 말고 확인한 사실과 안전한 fallback을 먼저 보고한다.

# AGENT.md

이 문서는 `mabimo-bot` 프로젝트에서 Codex/AI 에이전트가 작업할 때 따라야 할 기본 지침이다.
README, deep interview 결과, 구현 중 확정된 결정사항을 우선순위 높은 작업 기준으로 정리한다.

## 프로젝트 목적

마비노기 모바일 공식 홈페이지의 주요 게시판을 수집해 신규 게시글을 감지하고,
길드 Discord 서버에 자동 알림을 보내는 봇을 만든다.

장기 목표는 공지사항, 업데이트, 이벤트 게시판을 주기적으로 감시하고,
중복 알림 없이 필요한 정보를 빠르게 전달하는 것이다.

## 작업 원칙

- 작게 시작하고, 동작하는 세로 흐름을 먼저 완성한다.
- 불필요한 확장은 뒤로 미룬다.
- 현재 단계의 명확한 범위를 벗어나는 기능은 임의로 구현하지 않는다.
- 기존 코드 구조와 README의 의도를 우선한다.
- 구현 전에 현재 브랜치와 변경 상태를 확인한다.
- 작업 전에는 오늘 날짜의 데일리 로그 파일이 있는지 확인한다.
- 사용자가 만든 변경사항은 되돌리지 않는다.
- 실행 산출물과 로컬 비밀값은 커밋 대상에서 제외한다.

## 데일리 로그 기준

- 작업일별 로그는 `docs/` 아래 Markdown 파일로 기록한다.
- 파일명은 다음 세 가지로 분리한다.
  - `yyyy-mm-dd_daily_work.md`: 진행한 작업과 다음 작업
  - `yyyy-mm-dd_daily_success.md`: 성공한 내용과 검증 결과
  - `yyyy-mm-dd_daily_fail.md`: 실패하거나 막힌 내용과 후속 처리
- 작업 전에는 해당 날짜의 세 로그 파일 존재 여부와 기존 내용을 확인한다.
- 작업 후에는 실제로 진행한 내용, 성공한 검증, 실패나 차단 사항을 각각 알맞은 파일에 추가한다.
- 테스트 실패, 샌드박스/네트워크 제한, 승인 필요로 중단된 명령도 실패 로그에 남긴다.
- 사용자가 로그 기록 방식을 바꾸면 이 섹션과 기존 로그 파일 구조를 함께 갱신한다.

## 에이전트 워크플로우

- 메인 Codex는 coordinator 역할을 맡고, 작업 분해, 순서 결정, 최종 통합 검토를 책임진다.
- 구현 작업이 단순 기계 수정이 아니면 backend worker sub-agent에 위임한다.
- backend worker는 `.codex/agents/worker-backend.md`를 따르며, TDD를 기본 절차로 사용한다.
- 보안, 신뢰성, 아키텍처, PR 검증은 read-only explorer/reviewer sub-agent에 위임한다.
- reviewer는 `.codex/agents/reviewer-security.md`를 따르며, 직접 파일을 수정하지 않는다.
- coordinator는 구현 전에 다음 파일을 확인한다.
  - `AGENT.md`
  - `.codex/memories/mabimo-bot-agent-workflow.md`
  - 관련 `.codex/agents/*.md`
- coordinator는 worker가 소유한 구현을 동시에 중복 구현하지 않는다.
- worker 작업 지시에는 담당 파일이나 모듈 범위를 명시한다.
- worker 결과를 수락하기 전에 coordinator는 `git status --short --branch`, `git diff`, focused tests, broader verification을 확인한다.
- secret, DB 파일, `.venv`, cache/build artifact, 관련 없는 파일이 변경 범위에 섞이지 않았는지 확인한다.

## 브랜치 전략

이 프로젝트는 Git Flow 기반 브랜치 전략을 따른다.

- `main`은 운영용 브랜치이다.
  - 실제 배포 기준은 `main`이다.
  - 안정화되고 검증된 코드만 반영한다.
  - 일반 기능 개발이나 실험 작업을 `main`에서 직접 수행하지 않는다.
- `dev`는 개발 통합 브랜치이다.
  - feature 브랜치의 기본 분기점이자 병합 대상이다.
  - 운영 반영 전 테스트, 리뷰, 문서 정리의 기준점이다.
- `feature/*`는 단위 기능 개발 브랜치이다.
  - 항상 `dev`에서 분기한다.
  - 이름은 작업 단위가 드러나게 짓는다.
  - 예: `feature/notice-mvp`, `feature/remove-summary`, `feature/scheduler`
  - 작업 완료 후 `dev`로 병합한다.
- `release/*`는 운영 반영 준비 브랜치이다.
  - 운영 반영 전 별도 안정화가 필요하면 `dev`에서 분기한다.
  - release 브랜치에서는 버전 문서, 배포 문서, 작은 안정화 수정만 수행한다.
  - 검증 후 `main`과 `dev` 양쪽에 병합한다.
- `hotfix/*`는 운영 긴급 수정 브랜치이다.
  - 운영 중인 `main`에서 분기한다.
  - 수정 완료 후 `main`에 먼저 병합하고, 같은 변경을 `dev`에도 병합한다.
- 운영 반영은 `dev` 또는 `release/*`에서 `main`으로 병합하는 방식으로 한다.
- `main`에 병합하기 전에는 반드시 `dev` 또는 `release/*`에서 전체 검증을 통과해야 한다.
- 커밋 전에는 `git status --short`로 변경 범위를 확인한다.

## 현재 구현 범위

현재 기본 수집 대상은 공지사항과 이벤트 게시판이다.

### 포함 범위

- `공지사항` 게시판 목록 수집
- `이벤트` 게시판 목록 수집
- 최신 N개 게시글 확보
- `(board_type, thread_id)` 기준 신규 글 판정
- SQLite 저장
- Discord Webhook 알림
- 수동 1회 실행 및 APScheduler 주기 실행
- 실행 결과 집계 출력

### 제외 범위

- 본문 상세 페이지 수집
- 본문 요약
- LLM 요약
- 기존 글의 `(추가)`, `(완료)` 등 제목 변경 감지
- 기존 글의 본문 변경 감지
- 게시글 버저닝
- 업데이트 게시판 수집
- Discord slash command 또는 사용자 인터랙션
- 관리자 기능

## 단계별 로드맵

### 1차: 공지사항 수동 알림 MVP

공지사항 목록 수집, `(board_type, thread_id)` 신규 감지, SQLite 저장, Discord Webhook 전송,
수동 실행 1회 흐름을 완성한다.

### 2차: 자동화

APScheduler를 붙여 5~10분 주기로 자동 실행한다.

### 3차: 게시판 확장

업데이트와 이벤트 게시판 수집을 추가한다.

### 4차: 배포 후 알림 안정화

실제 사용자 피드백을 바탕으로 메시지 포맷, 실패 처리, 중복 방지, 속도 체감을 개선한다.

### 보류: 기존 글 업데이트 감지와 버저닝

본문 해시 비교, 제목 변경, 상태 표시 변경, 본문 변경 감지와 버전 이력 저장은 추후 별도 기획에서 결정한다.

## 데이터 모델 기준

1차 MVP의 게시글 마스터 테이블은 `posts`이다. 발송 상태와 발송 이력은
`notification_deliveries`가 관리한다.

```text
thread_id     TEXT NOT NULL
board_type    TEXT NOT NULL
title         TEXT NOT NULL
category      TEXT
published_at  TEXT
url           TEXT NOT NULL
first_seen_at TEXT NOT NULL
PRIMARY KEY (board_type, thread_id)
```

필드 의미:

- `thread_id`: 공식 사이트 게시글 ID이다.
- `board_type`: 게시판 종류이며 현재 `notice`, `event`를 사용한다.
- `(board_type, thread_id)`: 게시판별 신규 판정 기준이다.
- `published_at`: 공식 사이트 목록에 표시된 날짜/기간 값이다. 공지사항은 작성일, 이벤트는 이벤트 기간을 저장한다.
- `first_seen_at`: 봇이 해당 게시글을 처음 발견한 시각이다.

알림 발송 테이블은 `notification_deliveries`이다.

```text
id
notification_type
channel_type
status
board_type
thread_id
title
url
message
attempt_count
created_at
last_attempt_at
sent_at
error_message
response_status_code
```

- 신규 게시글 Discord 알림은 `notification_type='new_post'`, `channel_type='discord'`를 사용한다.
- `status='pending'`이면 발송 대상이다.
- 성공 시 `status='sent'`, `sent_at`, `last_attempt_at`, `attempt_count`, `response_status_code`를 갱신한다.
- 실패 시 재시도를 위해 `status='pending'`을 유지하고 `attempt_count`, `last_attempt_at`, `error_message`, `response_status_code`를 기록한다.
- 테스트 발송도 기록할 수 있어 `posts` FK는 두지 않는다.

향후 버저닝은 `posts` 테이블을 직접 복잡하게 만들지 말고,
`board_type`, `thread_id`를 참조하는 별도 `post_versions` 테이블로 확장한다.

예상 확장 필드:

```text
id
thread_id
title
content_text
content_hash
detected_at
change_type
```

## 신규 감지 정책

- 최신 게시글 목록을 가져온다.
- 같은 `board_type` 안에서 DB에 같은 `thread_id`가 없으면 신규 글이다.
- 같은 `board_type` 안에서 DB에 같은 `thread_id`가 있으면 기존 글이다.
- 1차 MVP에서는 같은 `thread_id`의 제목/본문 변경을 감지하지 않는다.
- 신규 글은 Discord 전송 전에 먼저 DB에 저장한다.
- 신규 글 저장 시 해당 글의 `notification_deliveries` pending row를 만든다.
- Discord 전송 성공 시 해당 delivery를 `sent`로 갱신한다.
- Discord 전송 실패 시 delivery는 `pending`으로 남겨 재시도 가능하게 한다.
- 이후 실행에서 `notification_deliveries.status = 'pending'`인 row가 재전송 대상이 될 수 있다.

## Discord 알림 기준

환경변수:

```text
DISCORD_WEBHOOK_URL
```

1차 MVP 메시지 포맷:

```text
[공지사항]

제목: {title}
분류: {category}
작성일: {published_at}
링크: {url}
```

이벤트 메시지는 같은 `published_at` 값에 `작성일` 대신 `기간` 라벨을 사용한다.

알림 메시지는 목록에서 수집한 데이터만 사용한다. 상세 본문 수집, 본문 요약, LLM 요약은 현재 제품 방향에서 제외한다.

1차 MVP에서는 게시판별 Webhook 분리, 멘션, embed, slash command를 구현하지 않는다.

## 실행 기준

1차 MVP 수동 실행 명령:

```powershell
python app/main.py
python app/main.py run-once
```

APScheduler 자동 실행 명령:

```powershell
python app/main.py scheduler
python app/main.py scheduler --interval-minutes 5
```

최소 콘솔 출력:

```text
fetched: N
new: N
sent: N
failed: N
```

검증 시 권장 명령:

```powershell
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe app\main.py
```

`DISCORD_WEBHOOK_URL`이 없으면 실제 전송은 실패 집계로 남을 수 있다. 이 경우 delivery는
`pending` 상태로 남고 attempt/error 정보가 기록되는 것이 의도된 동작이다.

## 코드 구조 기준

- `app/collectors/`: 게시판 목록 수집
- `app/parsers/`: HTML 파싱 로직
- `app/repositories/`: SQLite 저장소 접근
- `app/services/`: 신규 감지, 알림 등 비즈니스 로직
- `app/utils/`: HTTP, logger 등 공통 유틸
- `app/main.py`: 수동 실행 및 scheduler 명령 entrypoint
- `app/scheduler.py`: APScheduler interval job 구성

## 문서 기준

- README는 전체 프로젝트 개요와 장기 로드맵을 담는다.
- `docs/interview-summary-notice-mvp.md`는 1차 MVP 인터뷰 요약이다.
- `.omc/specs/deep-interview-mabimo-notice-mvp.md`는 deep interview 기반 상세 명세이다.
- 구현 범위가 바뀌면 관련 문서도 함께 업데이트한다.

## 확장 리스크

- DB는 `(board_type, thread_id)` 복합 primary key를 사용한다. 같은 게시글 ID가 다른 게시판에서 재사용되어도 별도 게시글로 저장한다.
- 미등록 `board_type`은 알림 라벨 매핑 실패로 처리하고 공지사항으로 대체하지 않는다. 현재는 스키마 변경 없이 실패 집계와 로그에 남기며, pending 재시도 상태가 유지될 수 있다.

## 커밋 전 체크

- 현재 브랜치가 feature 브랜치인지 확인한다.
- `git status --short`로 의도하지 않은 변경이 있는지 확인한다.
- `.env`, `*.db`, `*.db-journal`, `.venv`는 커밋하지 않는다.
- 가능하면 `compileall`을 실행해 문법 오류를 확인한다.
- 실제 Discord 전송 테스트는 webhook 설정 여부와 사용자의 승인을 확인한다.

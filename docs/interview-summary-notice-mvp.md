# Mabimo Notice MVP Interview Summary

작성일: 2026-06-01
상태: 구현 승인

## 1차 MVP 목표

마비노기 모바일 공식 홈페이지의 `공지사항` 게시판에서 최신 게시글 목록을 가져오고,
SQLite에 저장된 `thread_id`와 비교해 신규 글만 Discord Webhook으로 알림한다.

1차 MVP는 수동 1회 실행으로 완료 기준을 잡는다.

## 확정 범위

- 수집 대상은 `공지사항` 게시판만 포함한다.
- 신규 글 판정 기준은 `thread_id` 하나만 사용한다.
- Discord 알림은 제목, 카테고리, 작성일자, URL만 포함한다.
- 실행 명령은 `python app/main.py`로 유지한다.
- 실행 결과는 `fetched`, `new`, `sent`, `failed` 집계를 출력한다.

## 제외 범위

- 본문 상세 페이지 수집
- 본문 요약
- LLM 요약
- 기존 글의 `(추가)`, `(완료)` 등 제목 변경 감지
- 기존 글의 본문 변경 감지
- 게시글 버저닝
- 업데이트/이벤트 게시판 수집
- APScheduler 주기 실행
- Discord Bot slash command 또는 사용자 인터랙션

## 단계별 로드맵

### 1차

공지사항 목록 수집, `thread_id` 기준 신규 감지, SQLite 저장, Discord Webhook 전송,
수동 실행 1회 흐름을 완성한다.

### 2차

APScheduler를 붙여 5~10분 주기로 자동 실행한다.

### 3차

업데이트/이벤트 게시판으로 수집 대상을 확장한다.

### 4차

배포 후 실제 사용자 피드백을 바탕으로 메시지 포맷, 실패 처리, 중복 방지, 속도 체감을 개선한다.

### 보류

기존 글의 제목 변경, 상태 표시 변경, 본문 해시 기반 변경 감지, 버저닝은 추후 별도 기획에서 결정한다.

## SQLite 스키마

### `posts`

| Column | Type | Meaning |
|--------|------|---------|
| `thread_id` | TEXT PRIMARY KEY | 공식 사이트 게시글 ID이자 신규 판정 기준 |
| `board_type` | TEXT | 1차 MVP에서는 `notice` |
| `title` | TEXT | 목록에서 수집한 제목 |
| `category` | TEXT | 목록에서 수집한 카테고리 |
| `published_at` | TEXT | 공식 사이트에 표시된 작성일자 |
| `url` | TEXT | 게시글 URL |
| `first_seen_at` | TEXT | 봇이 처음 발견한 시각 |
| `notified_at` | TEXT NULL | Discord 전송 성공 시각, 실패 또는 대기 시 NULL |

`published_at`은 공식 사이트의 게시글 작성일이고, `first_seen_at`은 봇의 최초 발견 시각이다.

## Discord 정책

환경변수:

```text
DISCORD_WEBHOOK_URL
```

메시지 포맷:

```text
[공지사항]

제목: {title}
분류: {category}
작성일: {published_at}
링크: {url}
```

전송 실패 정책:

- 신규 글은 Discord 전송 전에 먼저 DB에 저장한다.
- 전송 성공 시 `notified_at`을 기록한다.
- 전송 실패 시 `notified_at = NULL`로 남겨 추후 재시도 가능하게 한다.

## 향후 버저닝 고려

1차 MVP의 `posts` 테이블은 게시글의 마스터 레코드 역할을 한다.
향후 기존 글 수정 감지와 버저닝이 필요하면 `thread_id`를 기준으로 별도 `post_versions`
테이블을 추가한다.

예상 확장 테이블:

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | 버전 ID |
| `thread_id` | TEXT | 부모 게시글 ID |
| `title` | TEXT | 해당 버전의 제목 |
| `content_text` | TEXT | 상세 본문 텍스트 |
| `content_hash` | TEXT | 변경 감지용 해시 |
| `detected_at` | TEXT | 변경 감지 시각 |
| `change_type` | TEXT | `title_changed`, `content_changed`, `status_marker_changed` 등 |

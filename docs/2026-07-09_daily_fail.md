# 2026-07-09 Daily Fail

## 실패하거나 막힌 내용

- 최초 실제 이벤트 수집 확인 명령은 샌드박스 네트워크 제한으로 실패했다.
  - 이후 승인된 실행으로 공식 페이지 수집 검증을 완료했다.
- 단순 `.\.venv\Scripts\python.exe -m unittest` 실행은 테스트 디스커버리 설정 때문에 0개 테스트만 실행했다.
  - 이후 `unittest discover -s tests`로 전체 테스트를 실행했다.
- 이벤트 기간을 `기간:`으로 표시하도록 구현했지만, README/AGENT 일부 문구가 `작성일` 중심 설명으로 남아 있었다.
  - 이후 README/AGENT 문구를 현재 동작에 맞게 정리했다.
- 최초 `git merge --no-ff feature/event-board-alerts` 실행은 `.git/ORIG_HEAD.lock` 생성 권한 문제로 실패했다.
  - 승인된 권한으로 같은 병합 명령을 다시 실행해 성공했다.

# Deployment Policy

이 문서는 `mabimo-bot`의 운영 배포 방식과 환경변수 관리 원칙을 정리한다.
운영 환경에서는 로컬 개발 편의를 위해 사용하는 `.env` 파일을 그대로 커밋하거나 코드 배포 디렉터리에 섞어 두지 않는다.

## 기본 원칙

- 로컬 개발에서는 `.env` 파일을 사용할 수 있다.
- `.env`는 Git ignore 상태를 유지하고 커밋하지 않는다.
- 운영에서는 OS 환경변수 또는 서비스 전용 env 파일을 사용한다.
- 운영 secret은 로그, 문서, 커밋, PR 설명, 이슈 본문에 노출하지 않는다.
- SQLite DB 파일은 코드 배포 디렉터리가 아니라 persistent data directory에 둔다.

## 환경변수

| 변수 | 용도 | 운영 정책 |
|------|------|-----------|
| `DISCORD_WEBHOOK_URL` | Discord webhook secret | 운영 로그, 문서, 커밋에 노출 금지 |
| `MABIMO_DB_PATH` | SQLite DB 영속 경로 | 코드 디렉터리가 아닌 persistent data directory 권장 |
| `LOG_LEVEL` | 로그 레벨 | 선택값. 미설정 시 `INFO`, 문제 분석 시 일시적으로 `DEBUG` |

`DISCORD_WEBHOOK_URL`은 secret이다. 예시 문서에는 실제 값을 넣지 말고 `https://discord.com/api/webhooks/...`처럼 마스킹된 형태만 사용한다.

## 로컬 개발

로컬 개발에서는 프로젝트 루트의 `.env`를 사용할 수 있다.

```text
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
MABIMO_DB_PATH=mabimo.db
LOG_LEVEL=DEBUG
```

로컬의 `mabimo.db`는 개발용 데이터로 취급한다. 운영 데이터와 공유하지 않는다.

수동 1회 실행:

```powershell
python app/main.py
python app/main.py run-once
```

스케줄러 실행:

```powershell
python app/main.py scheduler
python app/main.py scheduler --interval-minutes 5
```

## 운영 실행 명령

운영에서 반복 실행할 때는 scheduler 명령을 사용한다.

```bash
python app/main.py scheduler
```

수동 확인이나 즉시 1회 실행이 필요하면 다음 명령을 사용한다.

```bash
python app/main.py
python app/main.py run-once
```

Discord Webhook 연결만 확인해야 할 때는 테스트 발송 명령을 사용한다. 이 명령은 공식 게시글을 수집하지 않고, `posts`에도 데이터를 저장하지 않는다. 발송 이력은 `notification_deliveries`에 `notification_type='test'`로만 저장한다.

```bash
python app/main.py send-test
python app/main.py send-test --message "운영 디스코드 웹훅 테스트"
```

## Windows 배포 예시

PowerShell 세션에서만 적용되는 환경변수 예시:

```powershell
$env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
$env:MABIMO_DB_PATH = "C:\ProgramData\mabimo-bot\mabimo.db"
$env:LOG_LEVEL = "INFO"
python app/main.py scheduler
```

사용자 환경변수로 저장해야 하는 경우:

```powershell
[Environment]::SetEnvironmentVariable("MABIMO_DB_PATH", "C:\ProgramData\mabimo-bot\mabimo.db", "User")
[Environment]::SetEnvironmentVariable("LOG_LEVEL", "INFO", "User")
```

`DISCORD_WEBHOOK_URL`도 같은 방식으로 저장할 수 있지만, 화면 공유, 명령 히스토리, 운영 절차 문서에 노출되지 않도록 주의한다.

장기 실행 방식 선택지:

- Windows 작업 스케줄러: 로그인 또는 부팅 시 `python app/main.py scheduler`를 실행하도록 등록한다.
- NSSM: Python scheduler 프로세스를 Windows 서비스로 등록해 자동 재시작과 로그 경로를 관리한다.

작업 스케줄러나 NSSM을 사용할 때도 DB 경로는 코드 배포 디렉터리 밖의 `C:\ProgramData\mabimo-bot\mabimo.db` 같은 위치를 권장한다.

## Linux 배포 예시

서비스 전용 env 파일 예시:

```ini
# /etc/mabimo-bot.env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
MABIMO_DB_PATH=/var/lib/mabimo-bot/mabimo.db
LOG_LEVEL=INFO
```

`/etc/mabimo-bot.env`는 운영 서버에만 두고 Git에 커밋하지 않는다. 파일 권한은 서비스 계정만 읽을 수 있게 제한한다.

systemd unit 예시:

```ini
# /etc/systemd/system/mabimo-bot.service
[Unit]
Description=Mabimo Bot Scheduler
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/mabimo-bot
EnvironmentFile=/etc/mabimo-bot.env
ExecStart=/usr/bin/python app/main.py scheduler
Restart=always
RestartSec=10
User=mabimo-bot
Group=mabimo-bot

[Install]
WantedBy=multi-user.target
```

적용 예시:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mabimo-bot.service
sudo systemctl status mabimo-bot.service
```

## DB 영속성

SQLite 데이터는 `MABIMO_DB_PATH`가 가리키는 `mabimo.db` 파일에 저장된다. 이 파일이 유지되면 프로세스를 재기동하거나 코드를 다시 배포해도 기존 게시글 기록과 알림 상태가 유지된다.

운영에서는 코드 배포 디렉터리와 DB 디렉터리를 분리한다.

- 코드 예시: `/opt/mabimo-bot`, `C:\Services\mabimo-bot`
- DB 예시: `/var/lib/mabimo-bot/mabimo.db`, `C:\ProgramData\mabimo-bot\mabimo.db`

백업 대상은 `mabimo.db`이다. 배포 중 코드 디렉터리를 교체하거나 정리하더라도 DB 디렉터리는 삭제하지 않는다.

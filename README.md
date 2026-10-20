# Hawawa Dosiyo

Python과 Discord.py 2.x로 개발하는 Discord 서버 운영 봇입니다. 슬래시 명령어, 서버별 SQLite 저장, 재시작 후 복구되는 예약 작업과 버튼 기능을 제공합니다.

[한국어 안내](#시작하기) · [English](#english) · [상세 운영 가이드](docs/operations-guide.md) · [개발 진행표](docs/feature-roadmap.md)

## 주요 기능

- 사용자·서버·권한 조회, 투표, 랜덤 팀, 간단한 게임
- 환영·퇴장 안내, 자동·기간·지연 역할과 재입장 역할 복원
- 건의 투표·승인/반려, 추첨·재추첨, 별 반응 추천 게시판
- 개인·반복 리마인더, 저장 응답, 자동 응답과 안내 메시지
- 경험치·순위·역할 보상, 경고 기록, 메시지 정리, Discord AutoMod 연계

현재 기능은 단계적으로 개발하고 있으며 Carl-bot 전체 명령어·옵션과 동등한 상태는 아닙니다. 외부 서비스 알림은 보류 중입니다.

## 시작하기

개발·CI 기준 환경은 **Python 3.13**입니다. 프로젝트 루트에서 실행하세요.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

처음 설정할 때만 예시 파일을 복사합니다. 기존 `.env`가 있으면 유지하세요.

```bash
cp .env.example .env
```

`.env`에 새 Discord 봇의 `DISCORD_TOKEN`과 테스트 서버 ID를 입력한 뒤 실행합니다.

```bash
python -m bot.main
```

Discord에서 `/ping`을 실행해 연결을 확인하세요. 코드나 환경 설정을 바꿨다면 `Ctrl+C`로 종료한 뒤 다시 실행합니다.

## 환경 설정

| 변수 | 용도 | 기본값 |
| --- | --- | --- |
| `DISCORD_TOKEN` | Discord 봇 토큰. 필수 | 없음 |
| `TEST_GUILD_ID` | 테스트 명령어를 등록할 서버 ID | 비어 있음 |
| `COMMAND_SYNC_SCOPE` | `auto`, `test`, `global`, `off` | `auto` |
| `ENABLE_MEMBER_EVENTS` | 입퇴장 이벤트·멤버 목록 사용 | `false` |
| `ENABLE_MESSAGE_CONTENT` | 채팅 내용에 따른 자동 응답 사용 | `false` |

동기화 범위는 다음과 같습니다.

- `auto`: 테스트 서버 ID가 있으면 해당 서버, 없으면 전역 등록
- `test`: 테스트 서버에만 등록. `TEST_GUILD_ID` 필수
- `global`: 전역 등록
- `off`: 명령어 동기화 생략

개발 중에는 `test`를 권장합니다. 범위를 바꿔도 이전 범위에 등록된 명령어가 자동 삭제되지는 않습니다.

### Discord Developer Portal 설정

환경변수와 함께 Developer Portal의 해당 Intent도 켜야 합니다.

| 기능 | 필요한 설정 |
| --- | --- |
| 환영·퇴장 안내, 멤버 입퇴장 로그, 자동·지연·복원 역할, 멤버 정렬 | **Server Members Intent** + `ENABLE_MEMBER_EVENTS=true` |
| 정확 일치 자동 응답 `/trigger` | **Message Content Intent** + `ENABLE_MESSAGE_CONTENT=true` |
| 현재 기능 전체 | Presence Intent 불필요 |

버튼 역할·경험치·하단 안내에는 Message Content Intent가 필요하지 않습니다. 봇에는 사용할 기능에 맞는 채널·역할 관리 권한을 부여하고, 관리할 역할보다 봇 역할을 위에 배치하세요.

## 명령어

`/help`에서 전체 목록을 페이지별로 확인하고, `/help command:명령어`로 옵션·기본값·사용 예시를 볼 수 있습니다.

선택지와 참가자는 **쉼표(`,`)**로 구분합니다. `/vote`는 무작위 선택이며, 여러 사람이 참여하는 투표는 `/poll`입니다.

### 기본·정보·게임

| 명령어 | 기능 |
| --- | --- |
| `/ping` | 연결 상태·지연 시간 |
| `/help` | 전체·개별 명령어 도움말 |
| `/serverinfo` | 서버 이름·멤버 수·생성일 |
| `/userinfo` | 사용자 정보·확인 가능한 서버 가입 정보 |
| `/avatar` | 서버 또는 계정 아바타 |
| `/charinfo` | 문자별 Unicode 코드·이름 |
| `/permissions` | 현재 채널에서 사용자 또는 봇의 주요 적용 권한 |
| `/members` | 계정 생성일·가입일 기준 멤버 정렬 |
| `/roll` | 주사위 굴리기 |
| `/vote` | 선택지 중 무작위 선택 |
| `/randomteam` | 균등한 무작위 팀 배정 |
| `/coinflip` | 동전 던지기 |
| `/rps` | 가위바위보 |

### 커뮤니티·예약·역할

| 명령어 | 기능 |
| --- | --- |
| `/poll` | Discord 기본 공개 투표 |
| `/suggest` | 설정한 채널에 건의와 투표 버튼 게시 |
| `/suggestion` | 건의 조회·승인·반려. 처리자 서버 닉네임 표시 |
| `/giveaway` | 버튼 참가 추첨·목록·마감·재추첨 |
| `/starboard` | 별 반응 추천 게시판 설정 |
| `/reminder` | DM 리마인더 생성·목록·취소·반복 |
| `/autorole` | 입장 시 일반 역할 자동 지급 |
| `/rolepanel` | 공개 역할 받기·해제 버튼 생성 |
| `/rolepaneldisable` | 역할 패널 비활성화 |
| `/temprole` | 일반 역할 지급 후 기간 만료 시 회수 |
| `/roleautomation` | 입장 후 지연 지급·재입장 역할 복원 |
| `/rank` | 사용자 경험치·레벨 |
| `/leaderboard` | 서버 경험치 상위 순위 |
| `/levelreward` | 레벨별 일반 역할 보상 설정 |

### 서버 운영·관리

| 명령어 | 기능 |
| --- | --- |
| `/serverconfig` | 이벤트 로그·퇴장·건의 채널·경험치 설정 |
| `/welcome` | 환영 채널 설정 |
| `/greetingtemplate` | 환영·퇴장 문구 설정 |
| `/tag` | 응답 저장·조회·목록·삭제 |
| `/trigger` | 정확 일치 자동 응답 설정 |
| `/embed` | 안내 임베드 게시 |
| `/sticky` | 채널 하단 안내 설정·해제 |
| `/clear` | 최근 메시지 정리. 고정 메시지 보존 |
| `/modcase` | 경고 기록·조회·취소 |
| `/automod` | Discord 기본 금칙어·멘션 도배 차단 설정 |

기본 응답은 실행자에게만 표시됩니다. 공개 투표·건의·추첨·역할 패널·추천·안내 메시지는 채널에 게시되고, 리마인더는 개인 DM으로 전달됩니다. 채널 생성·삭제 로그는 채널 이름을 표시합니다.

권한 조건, 사용 예시, 입력 한도, 예약·보존 정책은 [상세 운영 가이드](docs/operations-guide.md)를 참고하세요.

## 구조

```text
bot/
  main.py          # 실행·Intent·모듈 로딩·명령어 동기화
  errors.py        # 슬래시 명령어 공통 오류 안내
  storage.py       # 서버별 SQLite 저장
  cogs/            # 기능별 명령어·이벤트·예약 작업
  __init__.py
tests/             # Discord 접속 없이 실행하는 자동 테스트
docs/
  operations-guide.md
  feature-roadmap.md
.github/workflows/test.yml
```

새 기능은 `bot/cogs/`에 Cog와 비동기 `setup(bot)`을 작성하고, `HawawaBot.setup_hook()`에서 동기화 전에 불러옵니다.

## 테스트와 CI

```bash
python -B -m unittest discover -s tests -v
```

테스트는 모의 Discord 객체와 임시 DB를 사용합니다. 실제 봇 토큰이나 기존 DB가 필요하지 않으며, 실제 Discord 연동 전체를 대신하지는 않습니다.

GitHub Actions는 `main` 대상 PR과 `main`·`feat/hawawa-v3-rebuild` Push에서 Python 3.13으로 동일한 테스트를 실행합니다. 필수 검사 이름은 `test`입니다.

## 데이터와 개발 원칙

- 서버별 설정·기록은 `data/hawawa-v3.db`에 저장합니다. 처음 사용할 때 생성되며, 같은 DB에는 봇 프로세스를 하나만 실행합니다.
- 토큰·`.env`·SQLite DB·`.venv`·Python 캐시는 Git에 올리지 않습니다. `.env.example`에는 예시 값만 기록합니다.
- 이전 통합 코드는 `archive/legacy-unified-2026` 브랜치에 보관합니다. 원본 Takoyaki·Dosiyo 저장소는 보관 처리했으며, 기존 봇·데이터는 이전 완료 전까지 보존합니다.
- 기존 `data/hawawa.db`는 자동으로 이전하지 않습니다. 데이터 이전은 새 구조가 안정화된 뒤 백업·복구 계획을 갖춘 별도 작업으로 진행합니다.
- 기능별로 구현·테스트하고 PR로 병합합니다. 파일 삭제·데이터 이전·커밋·Push·병합 전에는 사용자 확인 절차를 따릅니다.

진행 중인 범위와 제한은 [개발 진행표](docs/feature-roadmap.md), 작업 지침은 [AGENTS.md](AGENTS.md)에 정리되어 있습니다.

---

## English

Hawawa Dosiyo is a Discord server utility and community bot built with **Python 3.13, discord.py 2.x, and SQLite**. Commands are organized into Cogs and include information lookup, polls, games, reminders, roles, suggestions, giveaways, experience, and moderation tools.

### Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
# First setup only: preserve any existing .env
cp .env.example .env
# Set DISCORD_TOKEN and your test server ID locally
python -m bot.main
```

Use `/ping` to check the connection and `/help` for commands and examples. Separate choices and participants with commas. Restart after code or configuration changes.

- `COMMAND_SYNC_SCOPE`: `auto` (test guild when configured, otherwise global), `test`, `global`, or `off`. Test mode requires `TEST_GUILD_ID`. Changing scope does not remove registrations in other scopes.
- Enable **Server Members Intent** in Developer Portal and `ENABLE_MEMBER_EVENTS=true` for join/leave features and member inspection.
- Enable **Message Content Intent** and `ENABLE_MESSAGE_CONTENT=true` for text triggers. Presence Intent is not required.
- Data is stored per server in `data/hawawa-v3.db`; run one bot process per database. The legacy DB is not migrated.
- Replies are normally private; polls, suggestions, giveaways, role panels, starboard, and announcements publish channel messages. Reminders use DMs.
- Never commit tokens, `.env`, databases, virtual environments, or Python caches.

Run `python -B -m unittest discover -s tests -v` for offline tests. GitHub Actions reports the required `test` check. Use PRs to merge into `main`.

See the [operations guide (Korean)](docs/operations-guide.md) for permissions, limits, and recovery behavior, and the [roadmap (Korean)](docs/feature-roadmap.md) for remaining scope. This is an independent rebuild, not full Carl-bot feature parity. External integrations are deferred.

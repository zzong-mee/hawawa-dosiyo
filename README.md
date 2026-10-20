# Hawawa Dosiyo — v3 rebuild

This branch is a **clean rebuild** of the Discord bot. The previous integrated implementation is preserved in `archive/legacy-unified-2026`. Original Takoyaki and Dosiyo repositories remain untouched.

## Local quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env locally with your NEW Discord bot token
python -m bot.main
```

Try `/ping` in Discord. To sync the slash command immediately to a test server, set `TEST_GUILD_ID` in your local `.env` (server ID, not token).

**Security:** Never commit `.env`, tokens, or original SQLite databases. Never copy unaudited legacy Git history into this public repository.

## Command structure

- `bot/main.py`: starts the bot, loads extensions, and syncs slash commands.
- `bot/cogs/general.py`: defines `/ping`, `/help`, and `/serverinfo`.

All three commands reply only to the user who invoked them. `/help` lists the general commands. `/serverinfo` shows the server name, member count (including bots), and creation date, and is available only in servers.

Add general commands to the `General` Cog. For a new feature, create a module under `bot/cogs/` with an async `setup(bot)` function that registers its Cog, then load it in `HawawaBot.setup_hook()` before syncing commands. Restart the bot to load and sync changes.

### Utilities (no database)

`bot/cogs/utility.py` provides these commands:

| Command | Usage |
| --- | --- |
| `/userinfo` | Account name, ID, creation date and bot status; optional `user` defaults to yourself |
| `/avatar` | Avatar image; optional `user` defaults to yourself |
| `/roll` | Roll 1–20 dice with 2–1000 sides; defaults to one six-sided die |
| `/vote` | Pick from 2–20 unique options separated by `,`, up to 100 characters each |
| `/poll` | Public server poll with 2–10 unique options separated by `,`, up to 55 characters each; 1–168 hours, optional multiple answers |
| `/randomteam` | Split 2–40 unique participants separated by `,` into 2–10 balanced random teams; private response |

Utility responses are private except `/poll`, which publishes a native Discord poll in the channel. The bot needs permission to send messages and create polls. Discord stores the votes, so bot restarts do not erase a published poll. No local database is used.

Run offline tests with `python -B -m unittest discover -s tests -v`.

### Moderation

`bot/cogs/moderation.py` provides `/clear count:1–100` in server text channels and threads. It checks the caller's **Manage Messages** permission in the current channel at execution time. The bot also needs View Channel, Read Message History, and Manage Messages. It examines the requested number of messages sent before the command, preserves pinned messages, and privately reports the actual number deleted. Deletion is permanent; older messages may take longer because Discord requires individual deletion. No database is used.

## Plan

### Persistent server operations

`bot/cogs/community.py` uses a new `data/hawawa-v3.db`, separate from legacy `data/hawawa.db`. The DB is created on first use, stores server settings and saved replies by server ID, and survives bot restarts. Keep this file out of Git and back it up before future schema changes. Existing data is not migrated.

- `/tag action:set name:rules content:Read the rules`: save/update a reply (Manage Server required).
- `/tag action:show name:rules` or `/tag action:list`: private reply lookup/list.
- `/tag action:remove name:rules`: remove a saved reply (Manage Server required).
- `/welcome channel:#welcome`: enable a public welcome message for new human members (Manage Server required).
- `/autorole role:@Member`: enable one automatic role for new human members (Manage Roles required). Privileged/managed roles and roles at or above the bot or configuring member are rejected; the server owner is exempt from the configuring member's role hierarchy check.
- `/welcome disable:true` and `/autorole disable:true`: disable. Omit options to view current settings.

For welcome messages and auto roles, enable **Server Members Intent** in Discord Developer Portal, set `ENABLE_MEMBER_EVENTS=true` in local `.env`, and restart. This is opt-in; it is disabled by default. The bot must be able to view/send messages in the welcome channel and manage the chosen role. New settings apply to future joins only; missed joins while offline are not replayed. Deleted channels/roles are skipped, and event failures are logged. Command replies remain private; welcome events post publicly.

### Reminders and button roles

- `/reminder action:create minutes:30 text:Check the meeting`: DM reminder; at most 25 pending/sending reminders per user across servers. `/reminder action:list` shows the current server's reminders; `action:cancel reminder_id:123` cancels your pending/failed reminder.
- Reminders run every 15 seconds after the bot is ready, recover overdue deliveries after restart, and retry temporary HTTP failures up to three times. Enable DMs from the bot. Failed reminders appear in the list and are removed after seven days. A crash between DM delivery and database completion can produce a duplicate. Run only one bot process for this database. Cancellation cannot retract a delivery already in progress.
- `/rolepanel role:@Member title:Choose your role`: create a public role toggle button (Manage Roles required). The mapping is stored by server and message ID, and the persistent view is restored on startup without recreating messages. No Members Intent is needed for button clicks.
- `/rolepaneldisable message_id:123`: disable a panel in this server, preserving existing roles and the message. The button may remain visible but refuses further assignments. Deleted/privileged/unmanageable roles are rejected at click time.

### Server activities and native automatic moderation

- `/serverconfig feature:logs channel:#logs enabled:true`: log member joins/leaves and channel/role creation/deletion as IDs. Member events require the opt-in Members Intent. This is event logging, not audit-log attribution or message content archiving.
- `/serverconfig feature:goodbye channel:#goodbye enabled:true`: farewell messages (Members Intent required).
- `/serverconfig feature:suggestions channel:#suggestions enabled:true`, then `/suggest text:Your idea`: public suggestions, limited to one per minute per user/server. The author must be able to view the destination channel. New suggestions have persistent approve/disapprove vote buttons; `/suggestion action:approve|reject|show message_id:123` manages decisions (Manage Server required).
- `/serverconfig feature:levels enabled:true`: opt in to collecting message XP. Human messages award 10 XP per minute per user/server; bot/webhook/DM messages are excluded. `/rank` and `/leaderboard` show levels (100 XP per level). Disable with `enabled:false`; existing XP is retained. Message Content Intent is not required.
- `/automod kind:keywords action:set words:blocked1, blocked2` or `/automod kind:mentions action:set mentions:5`: create or update Discord-native message blocking rules. User and bot both need Manage Server. `action:show` displays enabled status; `action:disable` disables only this bot's named rule. Existing unrelated rules remain untouched. Native rules remain active even while the bot is offline; manage exceptions through Discord's AutoMod settings. Keyword set replaces this bot's keyword list.

### Temporary roles, giveaways, and starboard

- `/temprole member:@User role:@Trial minutes:60`: grant an ordinary role and revoke it after expiry, including overdue work after restart. Manage Roles is required; caller/bot hierarchy and privileged roles are checked. Existing permanent roles are not scheduled for removal. Repeating the command for a tracked role resets its expiry. Removal failures retry after a minute. This is timed removal, not Carl-bot's delayed-on-join role assignment. Do not manually repurpose a tracked role before its timer expires.
- `/giveaway action:create prize:Prize minutes:60 winners:1`: public join/leave buttons. Manage Server is required to create/list/end; members can use the buttons. `/giveaway action:list` shows up to 20 active giveaways; `action:end message_id:123` closes one early. Entries and frozen results persist. Completion edits the original message; failures retry without rerolling. All opted-in entrants are eligible, even if they later leave the server. `action:reroll message_id:123` rerolls within 30 days, excluding the immediately previous winners. Entries are retained for 30 days after closure/reroll, then cleaned by the worker; results remain. Eligibility filters, prize delivery, and participant export are not implemented. Keep message history permissions so the bot can edit old posts.
- `/starboard channel:#stars minimum:3`: link-only recommendations from public text channels after ⭐ reactions. Manage Server is required to configure. `/starboard disable:true` stops updates. Bot-authored posts and source channels hidden from `@everyone` are skipped. Reaction totals include the author's and bots' stars. Existing posts update on individual add/remove events and remain when below threshold; bulk reaction clears/source deletions are not reconciled. Content and attachments are never copied. Channel changes do not move old posts. A crash between sending a post and recording its ID can leave a duplicate.

Run one bot process per DB for background workers. These are representative implementations, not full Carl-bot parity. The public reference bot has further options and integrations beyond these implementations; see the scope and remaining limitations in the roadmap. External integrations are deferred at the user’s request.

### Additional local features and configuration

- `/modcase action:warn|list|show|revoke`: server-scoped warning history. Manage Messages required. Specify `member` and `reason` for warnings and `case_id` for inspection/revocation. Revocation retains original moderator/reason and records the revoker. Warning reasons are retained until a separate data cleanup is performed.
- `/roleautomation action:delay role:@Member minutes:60`: delayed role assignment for future joins; `remove` cancels that role's configuration and pending jobs; `list` shows up to 20 configurations. Manage Roles and Members Intent required for assignment. Configuration changes do not reschedule existing jobs.
- `/roleautomation action:restore enabled:true`: opt in to ordinary-role restoration on rejoin within 30 days; requires both Manage Roles and Manage Server. Snapshots are collected only after opt-in, exclude temporary/privileged/managed roles, and expire after 30 days. Safety and bot hierarchy are checked again when assigning. Disabling restoration stops future snapshots/restoration scheduling; already queued jobs can still run.
- `/trigger action:set keyword:hello response:Welcome {user}`: exact, case-insensitive automatic replies. Manage Server required. Enable Message Content Intent in Developer Portal and `ENABLE_MESSAGE_CONTENT=true` locally. `list` shows up to 15 entries, `remove` removes one; at most 100 per server. Replies have a 10-second channel cooldown and never ping mentions. Only `{user}` and `{server}` are replaced; no code/expressions are evaluated.
- `/embed title:Notice text:Welcome to {server}`: public announcement in the current channel (Manage Messages required).
- `/greetingtemplate kind:welcome|goodbye text:Welcome {user} to {server}`: customize join/leave notices; Manage Server required. Templates alone do not enable a channel/event.
- `/sticky text:Read the rules`: refresh a channel-bottom notice on human messages, at most once per 30 seconds. Manage Messages required. `disable:true` stops refreshing and leaves the last post. Old notices are deleted after the replacement is saved; deletion failures or a send/DB crash can leave old posts. No Message Content Intent needed.
- `/reminder ... repeat_minutes:60`: repeat after successful delivery; missed intervals are not replayed in a burst. Cancel with the existing reminder ID. A restart during creation between base reminder and repeat setting may leave a one-time reminder; verify the creation acknowledgement.
- `/levelreward action:set level:5 role:@Active`: reward an ordinary role at/above the configured level; Manage Roles required. `remove` removes configuration, preserving existing roles; `list` shows up to 25 entries. Awards are checked on the next XP-earning message and retried on later earning messages. No retroactive batch assignment or automatic role removal on level changes.
- `/coinflip`, `/rps choice:가위|바위|보`: private games.
- `/members order:oldest|youngest|newjoins|oldjoins count:10`: member sorting, up to 25 results. Manage Server, Members Intent, and a complete member cache required; incomplete results are rejected.

`COMMAND_SYNC_SCOPE=auto` preserves existing behavior. Use `test` to require `TEST_GUILD_ID`, `global` to sync globally, or `off` to skip synchronization. Changing scope does not delete commands previously registered in another scope. `/help` now has private owner-only page navigation and detailed parameter choices.

The new DB uses schema version 1 with additive table initialization; it rejects newer unknown schema versions. The legacy DB is never migrated. Repeated reminders, jobs, triggers, and role snapshots are scoped to the appropriate server/user. Most operational history/settings remain until explicitly removed; failed reminders expire after seven days, role snapshots after 30 days, and closed giveaway entrants after 30 days.

### Information inspection (no database)

`bot/cogs/information.py` adds private information commands:

- `/charinfo characters:가😀`: Unicode names, code points, and escaped representations of up to 15 code points, including invisible characters.
- `/permissions`: your effective permissions in the current server channel.
- `/permissions member:@user`: another server member's channel permissions.
- `/permissions bot:true`: the bot's current channel permissions.

`/permissions` shows common permissions rather than every Discord permission; role hierarchy and thread state can still restrict actions. These commands also appear in `/help` under information inspection.

See [the feature roadmap](docs/feature-roadmap.md) for the staged expansion based on Carl-bot's public feature categories. Full feature parity is not implemented. `/userinfo` includes available server member details, and `/avatar global_avatar:true` selects the account avatar.

Add functionality one module at a time with tests: core, moderation, music, economy, attendance, and server settings. Design an explicit, backed-up data migration only after the new schema is stable.

---

## 한국어 안내

### 프로젝트 소개

Hawawa Dosiyo는 Discord.py 2.x의 슬래시 명령어를 사용하는 Discord 봇입니다. 기존 통합 코드를 그대로 복사하지 않고 새롭게 설계하고 있습니다. 이전 코드는 `archive/legacy-unified-2026`에 보관하며, 기존 Takoyaki·Dosiyo 봇과 원본 리포지토리도 보존합니다.

### 로컬 실행

프로젝트 루트에서 처음 설정할 때 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

이미 `.env`가 있다면 복사 단계를 생략하고 기존 파일을 사용하세요. 로컬 `.env`에 새 봇의 `DISCORD_TOKEN`을 입력한 뒤 실행합니다.

```bash
python -m bot.main
```

개발할 때는 `.env`의 `TEST_GUILD_ID`에 테스트 서버 ID를 입력하세요. 설정하면 해당 서버에 명령어를 동기화하며, 비워두면 전역으로 동기화합니다. 코드 수정 후에는 실행 중인 봇을 `Ctrl+C`로 종료하고 다시 실행합니다.

**보안:** 토큰·`.env`·SQLite 데이터베이스는 커밋하거나 GitHub에 업로드하지 않습니다. `.env.example`에는 실제 비밀정보를 넣지 않습니다. 검토하지 않은 과거 Git 이력을 공개 저장소로 복사하지 않습니다.

### 코드 구조와 도움말

- `bot/main.py`: 봇 실행, 기능 모듈 로딩, 명령어 동기화
- `bot/cogs/general.py`: `/ping`, `/help`, `/serverinfo`
- `bot/cogs/utility.py`: 사용자 정보, 아바타, 주사위, 무작위 선택, 투표, 팀 배정
- `bot/cogs/moderation.py`: 메시지 삭제
- `bot/cogs/information.py`: 문자 정보와 채널 권한 조회
- `bot/cogs/community.py`: 태그, 환영 안내, 자동 역할
- `bot/cogs/reminders.py`: 개인 리마인더와 예약 전송
- `bot/cogs/role_panels.py`: 버튼 역할 패널
- `bot/cogs/server_events.py`: 이벤트 기록, 건의, 경험치·순위
- `bot/cogs/automod.py`: Discord 기본 자동 관리 규칙 설정
- `bot/cogs/temporary_roles.py`: 기간 역할 지급·회수
- `bot/cogs/giveaways.py`: 버튼 참가 추첨과 자동 마감
- `bot/cogs/starboard.py`: 공개 메시지 추천 링크 게시판
- `bot/storage.py`: 서버별 SQLite 저장 처리

`/help`는 명령어를 기능별로 보여주며, `/help command:avatar`처럼 입력하면 옵션·기본값·사용 예시를 볼 수 있습니다. 새 기능은 `bot/cogs/`에 Cog와 비동기 `setup(bot)` 함수를 작성하고, `HawawaBot.setup_hook()`에서 동기화 전에 불러옵니다.

### DB 없이 사용하는 기본 기능

| 명령어 | 기능 |
| --- | --- |
| `/ping` | 봇 연결 상태와 지연 시간 |
| `/help` | 전체 명령어 목록 또는 개별 명령어 사용법 |
| `/serverinfo` | 서버 이름·봇을 포함한 멤버 수·생성일. 서버 전용 |
| `/userinfo` | 사용자 이름·ID·계정 생성일·봇 여부. 확인 가능한 경우 서버 표시 이름·가입일·역할도 표시 |
| `/avatar` | 아바타 이미지. `global_avatar:true`로 계정 아바타 선택 |
| `/roll` | 2~1,000면 주사위를 1~20개 굴리기. 기본값은 6면 1개 |
| `/vote` | 쉼표로 구분한 선택지 2~20개 중 하나를 무작위로 선택. 선택지당 최대 100자 |
| `/poll` | 서버 공개 투표. 선택지 2~10개, 선택지당 최대 55자, 1~168시간, 복수 선택 지원 |
| `/randomteam` | 쉼표로 구분한 참가자 2~40명을 2~10개 팀에 균등하게 무작위 배정 |
| `/charinfo` | 최대 15개 Unicode 코드 포인트의 이름·코드·이스케이프 표기 |
| `/permissions` | 현재 서버 채널의 주요 적용 권한. `member:@사용자` 또는 `bot:true`로 대상 선택 |

`/userinfo`와 `/avatar`의 사용자를 생략하면 본인을 대상으로 합니다. 선택지·참가자는 쉼표(`,`)로 구분하고 중복 없이 입력합니다. 예: `철수, 영희, 민수, 지수`.

공개 투표 외 위 명령어 응답은 실행자에게만 표시됩니다. 투표 결과는 Discord에 저장되므로 봇 재시작 후에도 남습니다. 봇에는 메시지 전송·투표 만들기 권한이 필요합니다. `/permissions`에 권한이 표시되어도 역할 서열이나 스레드 상태에 따라 실제 작업이 제한될 수 있습니다.

### 메시지 삭제

`/clear count:10`은 명령어 실행 전에 보낸 최근 10개 메시지를 확인해 고정 메시지를 제외하고 삭제합니다. 서버 텍스트 채널과 스레드에서 사용할 수 있습니다.

- 실행자: 현재 채널의 **메시지 관리** 권한 필요
- 봇: **채널 보기·메시지 기록 보기·메시지 관리** 권한 필요
- 실제 삭제 개수는 본인에게만 표시
- 삭제는 되돌릴 수 없으며, 오래된 메시지는 개별 삭제로 시간이 더 걸릴 수 있음

### 데이터 저장과 서버 운영

서버 설정과 저장 응답 등은 새 `data/hawawa-v3.db`에 서버 ID별로 분리해 저장하며 재시작 후에도 유지합니다. DB는 처음 사용할 때 생성됩니다. 기존 `data/hawawa.db`는 변경하거나 이전하지 않습니다. 새 DB도 Git에서 제외하고, 향후 구조 변경 전에는 백업합니다.

| 사용 예시 | 기능 및 권한 |
| --- | --- |
| `/tag action:set name:rules content:규칙을 읽어주세요` | 응답 저장·수정. 서버 관리 권한 필요 |
| `/tag action:show name:rules` | 저장 응답 조회 |
| `/tag action:list` | 현재 서버의 태그 목록 |
| `/tag action:remove name:rules` | 태그 삭제. 서버 관리 권한 필요 |
| `/welcome channel:#입장안내` | 신규 일반 멤버 환영 안내. 서버 관리 권한 필요 |
| `/autorole role:@멤버` | 신규 일반 멤버에게 역할 1개 자동 지급. 역할 관리 권한 필요 |

`/welcome disable:true`와 `/autorole disable:true`로 해제합니다. 옵션을 생략하면 현재 설정을 조회합니다. 자동 역할에는 관리 권한이 없는 일반 역할만 사용할 수 있으며, 봇과 설정자의 최상위 역할보다 낮아야 합니다. 서버 소유자는 설정자 역할 서열 검사에서 제외됩니다.

환영·퇴장 안내와 멤버 입퇴장 기록·자동 역할을 사용하려면 Discord Developer Portal에서 **Server Members Intent**를 켜고 로컬 `.env`에 다음을 설정한 뒤 재시작하세요.

```dotenv
ENABLE_MEMBER_EVENTS=true
```

기본값은 `false`입니다. 봇에는 안내 채널의 메시지 전송 권한과 자동 지급 역할을 관리할 권한이 필요합니다. 설정은 이후 입장에 적용하며, 봇이 꺼져 있던 동안 놓친 입장 이벤트는 복구하지 않습니다. 삭제된 채널·역할은 건너뛰고 처리 실패는 로그에 남깁니다. 안내 메시지는 공개 게시되며 설정 명령어의 응답은 본인에게만 표시됩니다.

### 리마인더

- `/reminder action:create minutes:30 text:약속 확인`: 30분 후 개인 DM 알림
- `/reminder action:list`: 현재 서버에서 본인이 만든 알림 목록
- `/reminder action:cancel reminder_id:123`: 본인의 대기·실패 상태 알림 취소

예약 시간은 1분~30일이며, 전체 서버를 합쳐 사용자당 대기·전송 중인 알림을 최대 25개까지 만들 수 있습니다. 봇의 DM을 받을 수 있도록 허용해주세요.

봇 준비 후 15초 간격으로 확인하며, 재시작 시 기한이 지난 알림을 복구합니다. 일시적인 HTTP 오류는 최대 3회 시도합니다. 실패한 알림은 목록에 남고 7일 후 삭제됩니다. DM 전송 직후 DB 처리 전에 강제 종료되면 중복 전송될 수 있으므로 같은 DB에는 봇 프로세스를 하나만 실행합니다. 이미 전송 중인 알림은 취소하거나 회수할 수 없습니다.

### 버튼 역할

- `/rolepanel role:@게임알림 title:알림 역할 선택`: 공개 역할 받기·해제 버튼 생성
- `/rolepaneldisable message_id:123`: 해당 서버의 패널 비활성화

두 설정 명령어에는 역할 관리 권한이 필요합니다. 서버·메시지 ID와 역할의 매핑을 저장하므로 재시작 후에도 기존 버튼이 작동합니다. 버튼 클릭에는 Members Intent가 필요하지 않습니다. 삭제된 역할, 관리 권한이 있는 역할, 봇이 관리할 수 없는 역할은 클릭 시에도 거부합니다.

비활성화해도 패널 메시지와 이미 지급한 역할은 유지합니다. 버튼이 화면에 남아 있어도 추가 지급·해제는 거부합니다.

### 서버 활동·경험치·자동 관리

서버 설정 변경에는 서버 관리 권한이 필요합니다.

| 사용 예시 | 기능 |
| --- | --- |
| `/serverconfig feature:logs channel:#로그 enabled:true` | 멤버 입퇴장·채널/역할 생성·삭제를 ID로 기록 |
| `/serverconfig feature:goodbye channel:#퇴장안내 enabled:true` | 퇴장 안내 |
| `/serverconfig feature:suggestions channel:#건의 enabled:true` | 공개 건의 채널 설정 |
| `/suggest text:주말 게임 모임을 열어요` | 건의 게시. 사용자·서버당 1분에 한 번 사용 가능 |
| `/serverconfig feature:levels enabled:true` | 메시지 경험치 수집 활성화 |
| `/rank` | 본인 레벨·경험치 조회. `member`로 다른 멤버 선택 가능 |
| `/leaderboard` | 현재 서버 경험치 상위 10명 |

기능은 `enabled:false`로 끌 수 있으며, 기존 경험치는 유지됩니다. 건의 작성자는 대상 채널을 볼 수 있어야 합니다. 새 건의에는 찬성·반대·취소 버튼이 붙습니다. 서버 관리자는 `/suggestion action:approve` 또는 `reject`에 메시지 ID와 사유를 지정해 처리하고, `show`로 조회합니다. 이벤트 기록은 메시지 본문 보관이나 감사 로그 행위자 추적을 포함하지 않습니다.

경험치는 일반 사용자의 메시지에 대해 사용자·서버별로 분당 10점을 지급하며, 봇·웹훅·DM 메시지는 제외합니다. 100점당 1레벨입니다. Message Content Intent는 필요하지 않습니다.

`/automod`는 Discord 기본 메시지 차단 규칙을 설정하며, 실행자와 봇 모두 서버 관리 권한이 필요합니다.

- `/automod kind:keywords action:set words:차단단어1, 차단단어2`: 금칙어 규칙 생성·변경
- `/automod kind:mentions action:set mentions:5`: 멘션 도배 차단 규칙 생성·변경
- `action:show`: 활성화 상태 조회
- `action:disable`: Hawawa가 만든 해당 규칙만 비활성화

금칙어 설정은 해당 규칙의 기존 단어 목록을 대체합니다. 다른 규칙은 변경하지 않습니다. Discord 기본 규칙이므로 봇이 꺼져 있어도 작동하며, 세부 예외는 Discord 서버 설정의 AutoMod에서 관리합니다. Discord의 권한·규칙 수 제한을 따릅니다.

### 테스트와 개발 계획

#### 추가 로컬 기능

| 명령어 | 용도와 조건 |
| --- | --- |
| `/modcase` | `warn` 경고 기록, `list` 최근 10개, `show` 개별 조회, `revoke` 취소. 메시지 관리 권한 필요. 취소해도 원본 사유·처리자와 취소자 ID를 보존 |
| `/roleautomation` | `delay` 입장 후 지연 지급, `remove` 해당 역할 설정·대기 작업 취소, `list` 설정 최대 20개. 역할 관리 권한·Members Intent 필요. 기존 예약의 시간은 설정 변경으로 갱신하지 않음 |
| `/roleautomation action:restore enabled:true` | 재입장 시 30일 이내 일반 역할 복원. 서버 관리·역할 관리 권한 모두 필요. 활성화 이후의 퇴장만 저장하며 기간 역할·관리 역할은 제외 |
| `/trigger` | `set` 자동 응답 저장, `list` 최대 15개 조회, `remove` 삭제. 서버 관리 권한 필요. 채팅 내용이 정확히 일치하면 응답하며 대소문자·앞뒤 공백 무시 |
| `/embed` | 현재 채널에 제목·본문을 갖춘 안내 게시. 메시지 관리 권한 필요 |
| `/greetingtemplate` | 환영·퇴장 문구 설정. 서버 관리 권한 필요. 문구 설정만으로 이벤트·채널이 활성화되지는 않음 |
| `/sticky` | 채널 하단 안내 갱신. 메시지 관리 권한 필요. 일반 메시지 발생 시 최소 30초 간격으로 갱신. `disable:true`는 마지막 게시물을 남기고 중지 |
| `/levelreward` | `set` 레벨별 일반 역할 보상, `remove` 설정 삭제, `list` 최대 25개 조회. 역할 관리 권한 필요 |
| `/coinflip`, `/rps` | 동전 던지기·가위바위보. 본인에게만 결과 표시 |
| `/members` | 계정 생성일·가입일 정렬, 최대 25명. 서버 관리 권한·Members Intent·완전한 멤버 캐시 필요 |

자동 응답은 기본적으로 꺼져 있습니다. 사용하려면 Developer Portal에서 **Message Content Intent**를 켜고 `.env`에 `ENABLE_MESSAGE_CONTENT=true`를 설정한 뒤 재시작하세요. 서버당 최대 100개이며 채널당 10초 간격으로 응답합니다. 봇·웹훅 메시지는 무시합니다. 템플릿은 `{user}`·`{server}`만 치환하며 코드·속성 접근을 실행하거나 멘션을 알림으로 보내지 않습니다.

`/reminder`에 `repeat_minutes:60`을 추가하면 성공적으로 전송한 뒤 60분 후 다시 예약합니다. 오프라인 중 지나간 반복 횟수를 몰아서 보내지 않습니다. 생성 중 강제 종료되면 일회성 예약만 남을 수 있으므로 완료 응답을 확인하세요.

복원 역할은 지급 시에도 안전성과 봇 서열을 확인합니다. 복원을 꺼도 이미 대기 중인 지급 작업은 실행될 수 있습니다. 레벨 보상은 다음 경험치 지급 메시지에서 적용하며, 설정 삭제는 기존 역할을 회수하지 않습니다. 하단 안내는 교체 후 이전 글을 삭제하므로 삭제 실패·전송 직후 종료 시 이전 글이 남을 수 있습니다.

동기화는 `COMMAND_SYNC_SCOPE=auto`가 기존 동작입니다. `test`는 테스트 서버 ID를 필수로 요구하고, `global`은 전역 등록, `off`는 동기화 생략입니다. 범위를 변경해도 이전 범위에 등록한 명령어는 자동 삭제하지 않습니다. `/help`의 이전·다음 버튼은 실행자만 사용할 수 있습니다.

새 DB는 버전 1의 테이블을 추가 생성하고, 지원하지 않는 미래 버전은 거부합니다. 기존 원본 DB 이전은 수행하지 않습니다. 설정·경고 등 운영 기록은 별도 정리 전까지 유지하며, 실패 리마인더는 7일, 복원용 역할 기록과 마감 추첨 참가 기록은 30일 후 작업자가 정리합니다.

#### 기간 역할·추첨·추천 게시판

- `/temprole member:@사용자 role:@체험멤버 minutes:60`: 일반 역할을 지급하고 만료 후 회수합니다. 역할 관리 권한이 필요하며 실행자·봇 역할 서열을 검사합니다. 기존에 갖고 있던 일반 역할에는 자동 회수를 예약하지 않습니다. 이 기능으로 이미 예약한 역할은 다시 실행하면 기한이 갱신됩니다. 재시작 후 만료된 역할도 회수하고, 권한 부족 등으로 실패하면 1분 후 재시도합니다. 입장 후 지연 지급과는 다른 기능입니다. 예약 중인 역할을 수동으로 영구 역할로 전환하지 마세요.
- `/giveaway action:create prize:참가자추첨 minutes:60 winners:1`: 공개 참가·취소 버튼을 만들며, 운영에는 서버 관리 권한이 필요합니다. 참가자와 결과는 저장되고, 재시작 후 기존 버튼과 자동 마감이 복구됩니다. `action:list`로 진행 중인 추첨 최대 20개를 조회하고, `action:end message_id:123`으로 조기 마감합니다. 결과는 원본 메시지를 수정해 알리며, 전송 실패 시 당첨자를 다시 뽑지 않고 재시도합니다. 참가 후 서버를 떠난 사용자도 대상에 포함됩니다. `action:reroll message_id:123`으로 30일 이내 재추첨할 수 있으며 직전 당첨자는 제외합니다. 참가 기록은 마감·재추첨 후 30일간 보관한 뒤 작업자가 정리하고, 추첨 결과는 유지합니다. 참가 조건·경품 지급·참가자 내보내기는 아직 지원하지 않습니다.
- `/starboard channel:#추천 minimum:3`: 공개 텍스트 채널에서 ⭐가 모인 메시지의 링크를 게시합니다. 설정에는 서버 관리 권한이 필요합니다. `disable:true`로 끕니다. `@everyone`이 볼 수 없는 채널과 봇 메시지는 제외하며 본문·첨부파일을 복사하지 않습니다. 반응 개수에는 작성자와 봇의 반응도 포함합니다. 개별 반응 추가·제거 시 기존 게시물의 수치를 갱신하고, 기준 미만이 되어도 게시물은 유지합니다. 전체 반응 지우기·원본 삭제는 자동 반영하지 않습니다. 채널 변경 시 기존 게시물은 이동하지 않으며, 전송 직후 DB 저장 전에 종료되면 중복될 수 있습니다.

기간 역할·추첨의 예약 처리를 위해 봇이 온라인이어야 하며, 같은 DB에는 프로세스를 하나만 실행합니다. 추첨 게시물에는 메시지 기록 보기 권한도 필요합니다.

Discord에 접속하지 않고 테스트하려면 가상환경을 활성화한 상태에서 실행합니다.

```bash
python -B -m unittest discover -s tests -v
```

현재는 Carl-bot 공개 기능을 참고해 단계적으로 구현하는 중이며, 전체 명령어와 옵션이 모두 구현된 것은 아닙니다. 핵심 로컬 기능은 아래 확장 명령어까지 추가했지만, 전체 Carl-bot 옵션과 동등한 상태는 아닙니다. 외부 연동은 사용자 요청으로 보류했으며, 고급 조건부 역할·감사 로그 행위자 추적·유료 서비스 운영 등은 구현 범위에 포함되지 않았습니다. 자세한 구현 범위와 제한은 [기능 확장 진행표](docs/feature-roadmap.md)를 참고하세요.

기능별 구현·테스트 후 PR로 병합하며, 기존 데이터 이전은 새 구조가 안정화된 뒤 백업·복구 계획을 갖춘 별도 작업으로 진행합니다.

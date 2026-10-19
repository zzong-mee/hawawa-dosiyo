import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import random
import datetime
from datetime import time
import io
import os
import matplotlib.pyplot as plt

# --- 한글 폰트 설정 ---
def set_korean_font():
    plt.rcParams['axes.unicode_minus'] = False
    if os.name == 'nt':  # Windows
        plt.rcParams['font.family'] = 'Malgun Gothic'
    else:  # Linux (Ubuntu 등)
        plt.rcParams['font.family'] = 'NanumGothic'

# --- 초성 추출 함수 ---
def get_chosung(text):
    CHOSUNG_LIST = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
    result = ""
    for char in text:
        if '가' <= char <= '힣':
            char_code = ord(char) - ord('가')
            result += CHOSUNG_LIST[char_code // 588]
        else:
            result += char
    return result

class VirtualStock(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = os.getenv("DATABASE_PATH", "data/hawawa.db")
        self.current_news = "구렁이 거래소가 활발하게 운영 중입니다."
        self.market_trend = 0
        
        set_korean_font()
        self.setup_database()
        
        # --- 매 10분 정각 스케줄 설정 (00, 10, 20, 30, 40, 50분) ---
        # 이 방식은 봇이 켜져 있는 동안 정확히 정각 단위로 실행되어 훨씬 깔끔합니다.
        self.update_times = [time(hour=h, minute=m) for h in range(24) for m in range(0, 60, 10)]
        self.update_stock_prices.start()

    def cog_unload(self):
        self.update_stock_prices.cancel()

    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def setup_database(self):
        """데이터베이스 초기 설정 및 종목 데이터 주입"""
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        # 1. 가상 주식 종목 정보 테이블
        cur.execute("""
            CREATE TABLE IF NOT EXISTS virtual_stocks (
                stock_name TEXT PRIMARY KEY,
                current_price INTEGER,
                last_price INTEGER,
                description TEXT,
                color_code TEXT,
                next_impact REAL DEFAULT 0.0
            )
        """)

        # 2. 주식 가격 히스토리 테이블 (뉴스 헤드라인 컬럼 포함 필수!)
        cur.execute("""
    CREATE TABLE IF NOT EXISTS stock_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        stock_name TEXT, 
        price INTEGER, 
        news_headline TEXT, 
        timestamp DATETIME -- DEFAULT 제거
        )
    """)

        # 3. 사용자 지갑 및 보유 주식 테이블
        cur.execute("CREATE TABLE IF NOT EXISTS user_wallets (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 1000000)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_stocks (
                user_id INTEGER, 
                stock_name TEXT, 
                amount INTEGER DEFAULT 0, 
                avg_price INTEGER DEFAULT 0, 
                PRIMARY KEY (user_id, stock_name)
            )
        """)
        
        # 4. 초기 종목 데이터 정의 (20개)
        stocks = [
            ('구렁이전자', 50000, 50000, '가전의 명가', '#2ecc71', 0.0),
            ('개굴건설', 15000, 15000, '연못 신도시 주역', '#3498db', 0.0),
            ('마우스식품', 2000, 2000, '치즈 가공 전문', '#f1c40f', 0.0),
            ('래빗로지스', 8500, 8500, '빠른 배송의 대명사', '#e67e22', 0.0),
            ('타이거시큐리티', 120000, 120000, '보안 솔루션', '#e74c3c', 0.0),
            ('베어인베스트', 45000, 45000, '든든한 투자 파트너', '#9b59b6', 0.0),
            ('폭스마케팅', 12000, 12000, '스마트한 홍보', '#ff9ff3', 0.0),
            ('울프캐피탈', 77000, 77000, '금융의 포식자', '#54a0ff', 0.0),
            ('판다미디어', 31000, 31000, '콘텐츠 제작소', '#1dd1a1', 0.0),
            ('호스엔터', 5500, 5500, '연예 기획사', '#ff6b6b', 0.0),
            ('스네이크소프트', 92000, 92000, 'OS 개발사', '#48dbfb', 0.0),
            ('라이언스틸', 64000, 64000, '철강 제조', '#ff9f43', 0.0),
            ('이글항공', 11000, 11000, 'LCC 항공사', '#00d2d3', 0.0),
            ('드래곤테크', 150000, 150000, '반도체 장비', '#5f27cd', 0.0),
            ('코알라뷰티', 18000, 18000, '코스메틱 브랜드', '#c8d6e5', 0.0),
            ('캣게임즈', 4200, 4200, '모바일 게임 개발', '#576574', 0.0),
            ('덕워터', 3500, 3500, '생수 및 음료', '#00a8ff', 0.0),
            ('몽키패션', 22000, 22000, '스트릿 의류', '#70a1ff', 0.0),
            ('부엉이에듀', 14000, 14000, '온라인 강의', '#78e08f', 0.0),
            ('사슴제약', 89000, 89000, '신약 개발', '#b8e994', 0.0)
        ]
        
        # 종목 데이터 삽입 (없을 때만)
        cur.executemany("INSERT OR IGNORE INTO virtual_stocks VALUES (?, ?, ?, ?, ?, ?)", stocks)
        
        # 5. 차트 초기 생성 오류 방지를 위한 더미 히스토리 주입
        # 데이터가 2개 미만이면 선이 그려지지 않으므로 최소 2개씩 넣습니다.
        for s_name, s_price, *rest in stocks:
            cur.execute("SELECT COUNT(*) FROM stock_history WHERE stock_name = ?", (s_name,))
            count = cur.fetchone()[0]
            if count < 2:
                # 초기 상장 데이터 2건씩 추가
                cur.execute("INSERT INTO stock_history (stock_name, price, news_headline) VALUES (?, ?, ?)", 
                            (s_name, s_price, None))
                cur.execute("INSERT INTO stock_history (stock_name, price, news_headline) VALUES (?, ?, ?)", 
                            (s_name, s_price, None))
        
        
        conn.commit()
        conn.close()
        print("✅ [시스템] 데이터베이스 구조 생성 및 초기 데이터 주입 완료.")

    def create_chart_img(self, data_dict, title, news_data=None):
        plt.figure(figsize=(12, 6))
        conn = self.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT stock_name, color_code FROM virtual_stocks")
        color_map = {row['stock_name']: row['color_code'] for row in cur.fetchall()}
        conn.close()

        is_single = len(data_dict) == 1  # 단일 종목 상세 보기인지 확인
        max_len = 0

        for name, prices in data_dict.items():
            if not prices: continue
            max_len = max(max_len, len(prices))
            color = color_map.get(name, '#7f8c8d')
            
            # 1. 먼저 해당 종목의 선을 그립니다.
            plt.plot(prices, label=name, color=color, linewidth=2, marker='o', markersize=2)

            # 2. ★ 중요: 현재 루프의 'name'이 뉴스 데이터의 '종목명'과 일치할 때만 마커를 찍습니다.
            if news_data and name in news_data:
                # news_data[name]은 [(인덱스, 헤드라인), ...] 형태여야 합니다.
                for idx, headline in news_data[name]:
                    # 인덱스가 현재 가격 데이터 범위 내에 있고, 헤드라인이 있을 때만!
                    if headline and idx < len(prices):
                        plt.text(idx, prices[idx], '!', 
                                 fontsize=10, 
                                 fontweight='bold',
                                 ha='center', 
                                 va='center',
                                 zorder=20, # 다른 선들보다 훨씬 위에 보이게 설정
                                 bbox=dict(boxstyle='circle,pad=0.2', 
                                           fc='yellow',      
                                           ec='black',       
                                           lw=1,             
                                           alpha=0.9))
                            
                        
        # --- x축 시간 라벨 설정 (안정화 버전) ---
        if max_len > 0:
            kst = datetime.timezone(datetime.timedelta(hours=9))
            now = datetime.datetime.now(tz=kst)
            base_time = now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0)
        
            # 모든 데이터 포인트에 대한 라벨 생성
            labels = []
            for i in range(max_len):
                label_time = base_time - datetime.timedelta(minutes=(max_len - 1 - i) * 10)
                labels.append(label_time.strftime('%H:%M'))

            # 데이터가 적을 때는 모든 라벨을 보여주고, 많아지면 60분 간격으로 표시
            if max_len <= 6:
                display_step = 1  # 데이터가 적으면 매 틱마다 표시
            else:
                display_step = 6  # 데이터가 많으면 1시간 간격
            
            # x축의 위치(ticks)를 명시적으로 지정
            ticks = list(range(0, max_len, display_step))
            
            # 마지막 시점(현재 시간)이 리스트에 없다면 강제로 추가 (그래프 우측 끝 표시용)
            if (max_len - 1) not in ticks:
                ticks.append(max_len - 1)
            
            # 중복 제거 및 정렬
            ticks = sorted(list(set(ticks)))
            
            # 설정된 ticks 위치에 해당하는 labels만 추출해서 적용
            plt.xticks(ticks, [labels[t] for t in ticks], rotation=0)
            
            # x축 범위(Limit)를 명확히 지정하여 잘림 방지
            plt.xlim(-0.5, max_len - 0.5)
        
        # 통합 차트일 때는 범례를 표시, 단일 종목일 때는 숨겨서 깔끔하게 유지 가능
        if not is_single:
            plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8)
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        return buf

    def generate_next_cycle_news(self, cursor):
    # (뉴스 내용, 시장 트렌드, 영향받는 종목, 변동폭)
    # 트렌드 값(1/-1)과 변동폭을 미세하게 조정하여 예측을 더 어렵게 만들었습니다.
        news_list = [
            # 1. 구렁이전자
            ("🟡 구렁이전자, 스마트폰에 AI 대신 '진짜 지능' 탑재 시도... 사용자들과 기싸움 중", 1, "구렁이전자, 0.05"),
            ("🟡 구렁이전자, '전력 효율 0%' 달성... 전기를 쓰지 않으면 작동도 안 함", -1, "구렁이전자", -0.03),
            # 2. 개굴건설
            ("🟡 개굴건설, 아파트 단지 지하에서 거대 늪지대 발견... '자연 친화적 공법'이라 주장", 1, "개굴건설", 0.08),
            ("🟡 개굴건설, '보이지 않는 벽' 시공 성공... 입주민들 집 못 찾아 고전 중", -1, "개굴건설", -0.06),
            # 3. 마우스식품
            ("🟡 마우스식품, 유통기한 없는 '영구 보존' 도시락 출시... 성분표에는 '비밀'만 적혀 있어", 1, "마우스식품", 0.04),
            ("🟡 마우스식품, '0칼로리' 실현 위해 공기만 들어있는 봉지 과자 출시", -1, "마우스식품", -0.05),
            # 4. 래빗로지스
            ("🟡 래빗로지스, 배달 속도 높이려 전 직원에 '텔레포트' 교육... 성공률은 아직 미지수", 1, "래빗로지스", 0.07),
            ("🟡 래빗로지스 배달원, '길이 너무 예뻐서' 배달 중단하고 산책 중", -1, "래빗로지스", -0.04),
            # 5. 타이거시큐리티
            ("🟡 타이거시큐리티, 보안 강화를 위해 '비밀번호 입력 금지' 정책 도입... 사장님도 로그인 불가", 1, "타이거시큐리티", 0.03),
            ("🟡 타이거시큐리티, 도둑과 '가위바위보'해서 이기면 문 열어주는 시스템 검토", -1, "타이거시큐리티", -0.07),
            # 6. 베어인베스트
            ("🟡 베어인베스트, '운'에 맡기는 투자 공식 발표... 본사 옥상에서 매일 기우제 시행", 1, "베어인베스트", 0.09),
            ("🟡 베어인베스트, '수익률이 너무 높아서 무섭다'며 전 직원 휴가 선언", -1, "베어인베스트", -0.08),
            # 7. 폭스마케팅
            ("🟡 폭스마케팅, 광고비를 소비자에게 청구하는 '역발상 마케팅' 시도... 커뮤니티 찬반 과열", 1, "폭스마케팅", 0.02),
            ("🟡 폭스마케팅, 홍보 문구를 '사지 마세요'로 변경... 매출 변화 없음", -1, "폭스마케팅", -0.02),
            # 8. 울프캐피탈
            ("🟡 울프캐피탈, 모든 지점의 현금을 종이학으로 접어 보관 중... '예술적 가치 상승' 기대", 1, "울프캐피탈", 0.06),
            ("🟡 울프캐피탈, '돈보다 중요한 건 마음'이라며 이자 대신 편지 발송", -1, "울프캐피탈", -0.10),
            # 9. 판다미디어
            ("🟡 판다미디어, 24시간 동안 정지 화면만 나오는 실험적 다큐 편성... 시청률 집계 불가", 1, "판다미디어", 0.04),
            ("🟡 판다미디어, 드라마 결말을 '꿈'으로 처리... 시청자들 본사 앞에서 시위 중", -1, "판다미디어", -0.05),
            # 10. 호스엔터
            ("🟡 호스엔터, 소속 연예인들 전원 '무소유' 선언하며 산속 수행... 컴백 날짜는 하늘의 뜻", 1, "호스엔터", 0.05),
            ("🟡 호스엔터, 신인 그룹 이름을 '이름없음'으로 확정... 검색 사이트 노출 안 됨", -1, "호스엔터", -0.04),
            # 11. 스네이크소프트
            ("🟡 스네이크소프트, 스스로 코드를 수정하는 '자아 있는 백신' 개발... 현재 개발자 PC 점령", 1, "스네이크소프트", 0.07),
            ("🟡 스네이크소프트, 마우스를 왼쪽으로 움직이면 오른쪽으로 가는 업데이트 실시", -1, "스네이크소프트", -0.06),
            # 12. 라이언스틸
            ("🟡 라이언스틸, 액체 상태로 유지되는 '흐물흐물한 철강' 개발... 건축업계 용도 몰라 당황", 1, "라이언스틸", 0.03),
            ("🟡 라이언스틸, 철강에서 장미 향기가 나게 하는 기술 개발... 공사장 분위기 반전", -1, "라이언스틸", -0.02),
            # 13. 이글항공
            ("🟡 이글항공, 연료 절감을 위해 승객들에게 '단체 날갯짓' 권고... 운동 효과 기대", 1, "이글항공", 0.04),
            ("🟡 이글항공, 구름 위에서 정차 후 '무궁화 꽃이 피었습니다' 게임 진행", -1, "이글항공", -0.08),
            # 14. 드래곤테크
            ("🟡 드래곤테크, 투명 드론 개발 성공했으나 개발자들도 어디 있는지 못 찾아 분실 처리", 1, "드래곤테크", 0.12),
            ("🟡 드래곤테크, '불 뿜는 노트북' 개발... 겨울철 난방 기구로 인기 급상승", -1, "드래곤테크", -0.09),
            # 15. 코알라뷰티
            ("🟡 코알라뷰티, 바르면 20시간 동안 깊은 잠에 빠지는 '강제 숙면 팩' 출시... 직장인 관심 집중", 1, "코알라뷰티", 0.06),
            ("🟡 코알라뷰티, 화장품 용기를 '열 수 없게' 제작... '아껴 쓰라는 깊은 뜻'", -1, "코알라뷰티", -0.04),
            # 16. 캣게임즈
            ("🟡 캣게임즈, 게임 캐릭터가 사용자에게 '잔소리'하는 기능 추가... 유저들 중독 증세", 1, "캣게임즈", 0.08),
            ("🟡 캣게임즈, 몬스터가 너무 귀여워서 차마 때릴 수 없다는 민원 폭주 중", -1, "캣게임즈", -0.05),
            # 17. 덕워터
            ("🟡 덕워터, 물을 마시면 몸에서 빛이 나는 '발광 생수' 개발... 야간 보행 안전에 도움", 1, "덕워터", 0.03),
            ("🟡 덕워터, 생수에서 미약한 찌개 맛 감지... '한국인 맞춤형' 주장", -1, "덕워터", -0.03),
            # 18. 몽키패션
            ("🟡 몽키패션, 거꾸로 입어야 완성되는 '리버스 수트' 발표... 패션 피플들 착용법 몰라 고전", 1, "몽키패션", 0.04),
            ("🟡 몽키패션, 옷감이 너무 얇아 입어도 입지 않은 것 같은 효과... 단속 대상 논란", -1, "몽키패션", -0.02),
            # 19. 부엉이에듀
            ("🟡 부엉이에듀, 전 과목 시험 문항을 '넌센스 퀴즈'로 교체 예고... 교육계 논란의 중심", 1, "부엉이에듀", 0.02),
            ("🟡 부엉이에듀 강사, 수업 중에 '사실 나도 잘 모른다'며 동영상 시청으로 대체", -1, "부엉이에듀", -0.05),
            # 20. 사슴제약
            ("🟡 사슴제약, 먹으면 목이 길어지는 영양제 출시... '위쪽 공기는 맑다'는 후기 잇따라", 1, "사슴제약", 0.15),
            ("🟡 사슴제약, 알약을 입에 넣으면 사슴 울음소리가 나는 '사운드 캡슐' 개발", -1, "사슴제약", -0.11)
        ]
            
        # 무작위 뉴스 선택 시 target(종목명)을 클래스 변수에 저장
        self.current_news, self.market_trend, target, impact = random.choice(news_list)
        self.current_target = target 
        
        if target:
            cursor.execute("UPDATE virtual_stocks SET next_impact = ? WHERE stock_name = ?", (impact, target))
            
    def find_stock(self, search_text):
        """종목 이름 또는 초성으로 주식을 찾습니다."""
        conn = self.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT stock_name, current_price FROM virtual_stocks")
        stocks = cur.fetchall()
        conn.close()

        search_chosung = get_chosung(search_text)
        for name, price in stocks:
            if search_text in name or search_chosung == get_chosung(name):
                return name, price
        return None, None

   # --- 10분마다 실행되는 루프 (수정본) ---
    @tasks.loop(time=[time(hour=h, minute=m) for h in range(24) for m in range(0, 60, 10)]) 
    async def update_stock_prices(self):
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        try:
            # 1. 먼저 이번 틱에 터질 뉴스를 예약합니다.
            self.generate_next_cycle_news(cur) 
            
            kst = datetime.timezone(datetime.timedelta(hours=9))
            now_kst = datetime.datetime.now(tz=kst).strftime('%Y-%m-%d %H:%M:%S')

            # 가격 변동 계산을 위한 데이터 호출
            cur.execute("SELECT stock_name, current_price, next_impact FROM virtual_stocks")
            stock_rows = cur.fetchall()
            
            for row in stock_rows:
                # row 변수 하나로 받고, 아래처럼 키값으로 접근하면 Unpack 에러가 절대 나지 않습니다.
                s_name = row['stock_name']
                s_price = row['current_price']
                s_impact = row['next_impact']

                # 변동폭 계산 로직
                change = random.uniform(-0.025, 0.025)
                if self.market_trend == 1: change += random.uniform(0.01, 0.04)
                elif self.market_trend == -1: change -= random.uniform(0.01, 0.04)
                
                # 새로운 가격 결정
                new_price = max(100, int(s_price * (1 + change + s_impact)))
                
                # DB 업데이트
                cur.execute("""
                    UPDATE virtual_stocks 
                    SET last_price = current_price, 
                        current_price = ?, 
                        next_impact = 0.0 
                    WHERE stock_name = ?
                """, (new_price, s_name))
                
                # 뉴스 헤드라인 기록 여부 체크
                headline = self.current_news if s_name == getattr(self, 'current_target', None) else None
                
                cur.execute("""
                    INSERT INTO stock_history (stock_name, price, news_headline, timestamp) 
                    VALUES (?, ?, ?, ?)
                """, (s_name, new_price, headline, now_kst))
                                
            # 2. 다음 뉴스 예약
            self.generate_next_cycle_news(cur)
            
            # 3. 랭킹 데이터 미리 추출 (Embed 전송용)
            cur.execute("""
                SELECT w.user_id, w.balance + TOTAL(s.amount * v.current_price) as total_asset 
                FROM user_wallets w 
                LEFT JOIN user_stocks s ON w.user_id = s.user_id 
                LEFT JOIN virtual_stocks v ON s.stock_name = v.stock_name 
                GROUP BY w.user_id ORDER BY total_asset DESC LIMIT 5
            """)
            ranking = cur.fetchall()
            conn.commit()

            # 4. 차트 데이터 추출 (최근 36틱 = 6시간)
            all_chart_data = {}
            cur.execute("SELECT stock_name FROM virtual_stocks")
            all_names = [r[0] for r in cur.fetchall()]
            for n in all_names:
                cur.execute("SELECT price FROM stock_history WHERE stock_name = ? ORDER BY id DESC LIMIT 36", (n,))
                prices = [r[0] for r in cur.fetchall()]
                all_chart_data[n] = prices[::-1]

        except Exception as e:
            print(f"❌ 주식 업데이트 오류: {e}")
            return
        finally:
            conn.close()

        # --- Discord 전송 로직 ---
        embed = discord.Embed(
            title="📊 구렁이 거래소 경제 리포트", 
            description=f"⏱️ 업데이트: {datetime.datetime.now().strftime('%H:%M')} (10분 주기)",
            color=discord.Color.blue()
        )
        
        # 1. 최근 1시간(6틱) 뉴스 추출
        conn = self.get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT news_headline, timestamp 
            FROM stock_history 
            WHERE news_headline IS NOT NULL 
            ORDER BY id DESC LIMIT 6
        """)
        recent_6_news = cur.fetchall()
        conn.close()

        # 뉴스 리스트 문자열 생성 (과거 -> 현재 순서)
        if recent_6_news:
            news_history_text = ""
            for r in reversed(recent_6_news):
                # DB에서 가져온 문자열을 파이썬 datetime 객체로 변환
                dt = datetime.datetime.strptime(r['timestamp'], '%Y-%m-%d %H:%M:%S')
        
                prefix = "🔥" if r['news_headline'] == self.current_news else "•"
                # dt.strftime('%H:%M')을 그대로 사용 (이미 KST로 저장했으므로)
                news_history_text += f"{prefix} `[{dt.strftime('%H:%M')}]` {r['news_headline']}\n"
        else:
            news_history_text = "최근 1시간 내 주요 뉴스가 없습니다."

        # 메인 섹션 구성
        embed.add_field(name="📢 실시간 주요 뉴스", value=f"## {self.current_news}", inline=False)
        embed.add_field(name="📜 최근 1시간 뉴스 기록", value=news_history_text, inline=False)
        
        # 2. 랭킹 데이터 (TOP 5)
        rank_text = ""
        for i, r in enumerate(ranking, 1):
            rank_text += f"**{i}위** <@{r['user_id']}> : `{int(r['total_asset']):,}원`\n"
        embed.add_field(name="🏆 자산 랭킹 (TOP 5)", value=rank_text or "참여 데이터 없음", inline=False)
        
        # 3. 통합 차트 전송 (6시간 추이 유지)
        chart_buf = self.create_chart_img(all_chart_data, "📈 전 종목 통합 추이 (최근 6시간)")
        
        for guild_id, config in self.bot.config_cache.items():
            if ch_id := config.get("news"):
                channel = self.bot.get_channel(ch_id)
                if not channel: continue
                try:
                    chart_buf.seek(0)
                    file = discord.File(chart_buf, filename="total_chart.png")
                    embed.set_image(url="attachment://total_chart.png")
                    
                    # 기존 리포트 메시지 삭제 (채널 도배 방지)
                    async for m in channel.history(limit=5):
                        if m.author == self.bot.user and "경제 리포트" in (m.embeds[0].title if m.embeds else ""):
                            await m.delete()
                            break
                    await channel.send(embed=embed, file=file)
                except Exception as e:
                    print(f"전송 실패: {e}")
        chart_buf.close()
        
    @app_commands.command(name="주식시세", description="전체 시세 상황판 또는 특정 종목의 12시간 상세 차트를 확인합니다.")
    async def stock_list(self, interaction: discord.Interaction, 종목: str = None):
        conn = self.get_db_connection()
        cur = conn.cursor()

        if 종목:
            # --- 1. 특정 종목 상세 보기 (차트 포함) ---
            name, price = self.find_stock(종목)
            if not name:
                conn.close()
                return await interaction.response.send_message(f"❌ '{종목}'을 찾을 수 없습니다.", ephemeral=True)
            
            # 12시간 분량(72개) 데이터와 뉴스 헤드라인을 함께 가져옴
            cur.execute("""
                SELECT price, news_headline 
                FROM stock_history 
                WHERE stock_name = ? 
                ORDER BY id DESC LIMIT 72
            """, (name,))
            rows = cur.fetchall()[::-1] # 시간순 정렬
            
            if not rows:
                conn.close()
                return await interaction.response.send_message("❌ 차트 데이터가 부족합니다.", ephemeral=True)

            history = [r['price'] for r in rows]
            
            # r['news_headline']이 실제 텍스트일 때만 리스트에 추가
            current_events = []
            for i, r in enumerate(rows):
                if r['news_headline'] and len(r['news_headline']) > 0:
                    current_events.append((i, r['news_headline']))
            
            news_events = {name: current_events}

            # 전 시점 가격 대비 변동폭 계산
            cur.execute("SELECT last_price FROM virtual_stocks WHERE stock_name = ?", (name,))
            last_p = cur.fetchone()['last_price']
            conn.close()

            diff = price - last_p
            rate = (diff / last_p * 100) if last_p != 0 else 0
            embed_color = discord.Color.red() if diff > 0 else discord.Color.blue() if diff < 0 else discord.Color.light_grey()
            sign = "🔺" if diff > 0 else "🔻" if diff < 0 else "🔹"

            # 차트 생성 (강조 기능 및 뉴스 마커 포함)
            chart_buf = self.create_chart_img({name: history}, f"🔍 {name} 12시간 분석 리포트", news_data=news_events)
            file = discord.File(chart_buf, filename="detail_chart.png")

            embed = discord.Embed(title=f"📊 {name} 상세 정보", color=embed_color, timestamp=datetime.datetime.now())
            embed.add_field(name="현재가", value=f"**{price:,}원**", inline=True)
            embed.add_field(name="전주기대비", value=f"{sign} {abs(diff):,}원 ({rate:.2f}%)", inline=True)
            
            # 최근 발생한 뉴스가 있다면 임베드에도 표시
            recent_news = [r['news_headline'] for r in rows if r['news_headline'] is not None]
            if recent_news:
                embed.add_field(name="📢 최근 주요 뉴스", value=f"· {recent_news[-1]}", inline=False)

            embed.set_image(url="attachment://detail_chart.png")
            embed.set_footer(text="노란색 '!' 표시는 뉴스가 발생한 시점입니다.")
            
            await interaction.response.send_message(embed=embed, file=file)
            
        else:
            # --- 2. 전체 시세 상황판 (목록) ---
            cur.execute("SELECT stock_name, current_price, last_price FROM virtual_stocks ORDER BY current_price DESC")
            stocks = cur.fetchall()
            conn.close()
            
            # 다음 변동까지 남은 시간 계산
            next_it = self.update_stock_prices.next_iteration
            time_str = "잠시 후"
            if next_it:
                rem = next_it - datetime.datetime.now(datetime.timezone.utc)
                m, s = divmod(max(0, int(rem.total_seconds())), 60)
                time_str = f"{m}분 {s}초"

            embed = discord.Embed(
                title="📈 구렁이 거래소 실시간 상황판", 
                description=f"⏱️ **다음 변동까지**: `{time_str}` (10분 간격)\n📰 **현재 뉴스**: `{self.current_news}`", 
                color=discord.Color.green()
            )
            
            for n, c, l in stocks:
                diff = c - l
                rate = (diff / l * 100) if l != 0 else 0
                sign = "🔺" if diff > 0 else "🔻" if diff < 0 else "🔹"
                
                embed.add_field(
                    name=n, 
                    value=f"**{c:,}원**\n{sign} {abs(diff):,} ({rate:.2f}%)", 
                    inline=True
                )
            
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="통합차트", description="전 종목의 추이를 비교합니다.")
    async def total_chart(self, interaction: discord.Interaction):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT stock_name FROM virtual_stocks")
        names = [r[0] for r in cur.fetchall()]
        all_data = {n: [r[0] for r in cur.execute("SELECT price FROM stock_history WHERE stock_name = ? ORDER BY id DESC LIMIT 72", (n,)).fetchall()][::-1] for n in names}
        conn.close()
        file = discord.File(self.create_chart_img(all_data, "📊 전 종목 통합 차트 (6시간)"), filename="total.png")
        await interaction.response.send_message(file=file)

    @app_commands.command(name="풀매수", description="가진 돈을 전부 털어 주식을 삽니다.")
    async def buy_all(self, interaction: discord.Interaction, 종목: str):
        name, price = self.find_stock(종목)
        if not name: return await interaction.response.send_message("❌ 존재하지 않는 종목입니다.", ephemeral=True)
        
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO user_wallets (user_id, balance) VALUES (?, 1000000)", (interaction.user.id,))
        cur.execute("SELECT balance FROM user_wallets WHERE user_id = ?", (interaction.user.id,))
        bal = int(cur.fetchone()[0])
        
        amt = bal // price
        if amt <= 0: 
            conn.close()
            return await interaction.response.send_message(f"❌ 잔액이 부족합니다. ({bal:,}원)", ephemeral=True)
        
        cost = amt * price
        cur.execute("UPDATE user_wallets SET balance = balance - ? WHERE user_id = ?", (cost, interaction.user.id))
        cur.execute("SELECT amount, avg_price FROM user_stocks WHERE user_id = ? AND stock_name = ?", (interaction.user.id, name))
        exist = cur.fetchone()
        
        if exist:
            new_total = exist[0] + amt
            new_avg = ((exist[0] * exist[1]) + cost) // new_total
            cur.execute("UPDATE user_stocks SET amount = ?, avg_price = ? WHERE user_id = ? AND stock_name = ?", (new_total, new_avg, interaction.user.id, name))
        else:
            cur.execute("INSERT INTO user_stocks VALUES (?, ?, ?, ?)", (interaction.user.id, name, amt, price))
        
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"🔥 **{name}** {amt}주 풀매수 완료! (-{cost:,}원)")

    @app_commands.command(name="풀매도", description="보유한 특정 주식을 전부 판매합니다.")
    async def sell_all(self, interaction: discord.Interaction, 종목: str):
        name, price = self.find_stock(종목)
        if not name: return await interaction.response.send_message("❌ 존재하지 않는 종목입니다.", ephemeral=True)
            
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT amount, avg_price FROM user_stocks WHERE user_id = ? AND stock_name = ?", (interaction.user.id, name))
        res = cur.fetchone()

        if not res or int(res[0]) <= 0:
            conn.close()
            return await interaction.response.send_message(f"❌ 보유 중인 **{name}** 주식이 없습니다.", ephemeral=True)

        amt, avg_p = int(res[0]), int(res[1])
        gain = amt * price
        profit = gain - (avg_p * amt)
        rate = ((price - avg_p) / avg_p * 100) if avg_p != 0 else 0

        cur.execute("DELETE FROM user_stocks WHERE user_id = ? AND stock_name = ?", (interaction.user.id, name))
        cur.execute("UPDATE user_wallets SET balance = balance + ? WHERE user_id = ?", (gain, interaction.user.id))
        conn.commit()
        conn.close()

        sign = "📈 수익" if profit >= 0 else "📉 손해"
        await interaction.response.send_message(f"💰 **{name}** 매도 완료!\n💵 +{gain:,}원 | {sign} {profit:,}원 ({rate:.2f}%)")

    @app_commands.command(name="지갑", description="보유 자산 및 수익률을 확인합니다.")
    async def my_wallet(self, interaction: discord.Interaction):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO user_wallets (user_id) VALUES (?)", (interaction.user.id,))
        cur.execute("SELECT balance FROM user_wallets WHERE user_id = ?", (interaction.user.id,))
        bal = cur.fetchone()[0]
        cur.execute("SELECT s.stock_name, s.amount, s.avg_price, v.current_price FROM user_stocks s JOIN virtual_stocks v ON s.stock_name = v.stock_name WHERE s.user_id = ? AND s.amount > 0", (interaction.user.id,))
        stocks = cur.fetchall()
        conn.close()

        total_buy, total_val = 0, 0
        embed = discord.Embed(title=f"💰 {interaction.user.display_name}의 지갑", color=discord.Color.gold())
        embed.add_field(name="💵 보유 현금", value=f"**{bal:,}원**", inline=False)
        
        for n, amt, avg, curr in stocks:
            total_buy += amt * avg
            total_val += amt * curr
            
            # 수익률 계산
            rate = ((curr - avg) / avg * 100) if avg != 0 else 0
            
            # --- [수정된 이모지 로직] ---
            if rate > 0:
                sign = "🔺" # 상승: 빨간 화살표 위쪽
                color_text = "수익"
            elif rate < 0:
                sign = "🔻" # 하락: 파란 화살표 아래쪽 (이 부분이 수정되었습니다)
                color_text = "손실"
            else:
                sign = "🔹" # 보합: 파란 사각형
                color_text = "변동 없음"
            # --------------------------

            embed.add_field(
                name=f"{n} ({amt}주)", 
                value=f"{sign} **{rate:.2f}%** ({color_text})\n평단: {avg:,} | 현재: {curr:,}", 
                inline=False
            )

        if total_buy > 0:
            profit = total_val - total_buy
            total_rate = (profit / total_buy * 100)
            
            # 전체 손익에도 화살표 적용
            total_sign = "🔺" if profit > 0 else "🔻" if profit < 0 else "🔹"
            
            embed.add_field(
                name="📊 총 주식 평가", 
                value=f"손익: {total_sign} {profit:,}원 ({total_rate:.2f}%)", 
                inline=False
            )
        elif not stocks:
            embed.add_field(name="알림", value="보유 중인 주식이 없습니다.", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="랭킹", description="자산 순위 TOP 10을 확인합니다.")
    async def stock_ranking(self, interaction: discord.Interaction):
        await interaction.response.defer()
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT w.user_id, w.balance + TOTAL(s.amount * v.current_price) as total_asset FROM user_wallets w LEFT JOIN user_stocks s ON w.user_id = s.user_id LEFT JOIN virtual_stocks v ON s.stock_name = v.stock_name GROUP BY w.user_id ORDER BY total_asset DESC LIMIT 10")
        ranking = cur.fetchall()
        conn.close()

        embed = discord.Embed(title="🏆 구렁이 거래소 자산 랭킹", color=discord.Color.gold())
        for i, (uid, asset) in enumerate(ranking, 1):
            user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
            name = user.display_name if user else f"유저({uid})"
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}위.**"
            embed.add_field(name=f"{medal} {name}", value=f"총 자산: **{int(asset):,}원**", inline=False)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(VirtualStock(bot))
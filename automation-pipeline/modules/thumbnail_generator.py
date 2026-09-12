"""
골든라이프(GoldenLife) 블로그 게시글 전용 고해상도 SVG 썸네일 자동 생성 모듈
1200x630 규격, 6070 시니어 맞춤형 품격 있는 골드/에메랄드/슬레이트 감성, 19대 테마별 벡터 일러스트레이션 지원
"""
import os
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "blog-frontend" / "public" / "images" / "thumbnails"
DEFAULT_DIST_DIR = Path(__file__).resolve().parents[2] / "blog-frontend" / "dist" / "images" / "thumbnails"

# 카테고리별 컬러 팔레트 & 뱃지 스타일
CATEGORY_CONFIG = {
    "정부지원금 & 복지": {
        "bg_stops": [("#064e3b", "0%"), ("#0f766e", "50%"), ("#042f2e", "100%")],
        "accent": "#34d399",
        "pill_bg": "#064e3b",
        "pill_border": "#10b981",
        "pill_text": "#a7f3d0",
        "badge": "2026 복지 지원금"
    },
    "연금 & 절세 상식": {
        "bg_stops": [("#0f172a", "0%"), ("#1e293b", "50%"), ("#090d16", "100%")],
        "accent": "#fbbf24",
        "pill_bg": "#451a03",
        "pill_border": "#f59e0b",
        "pill_text": "#fef3c7",
        "badge": "2026 연금·절세 공식"
    },
    "시니어 건강 & 일상": {
        "bg_stops": [("#14532d", "0%"), ("#15803d", "50%"), ("#052e16", "100%")],
        "accent": "#ca8a04",
        "pill_bg": "#1c1917",
        "pill_border": "#eab308",
        "pill_text": "#fef08a",
        "badge": "100세 건강 솔루션"
    }
}

def escape_xml(s: str) -> str:
    return (str(s).replace("&", "&amp;")
                  .replace("<", "&lt;")
                  .replace(">", "&gt;")
                  .replace('"', "&quot;")
                  .replace("'", "&apos;"))

def split_title(title: str, max_len=18):
    words = title.split()
    lines = []
    curr = ""
    for w in words:
        if len(curr + " " + w) > max_len and curr:
            lines.append(curr.strip())
            curr = w
        else:
            curr = (curr + " " + w).strip()
    if curr:
        lines.append(curr.strip())
    if len(lines) > 3:
        lines = lines[:2] + [lines[2] + "..."]
    return lines

def classify_post(post_data: Dict[str, Any]) -> str:
    title = post_data.get("title", "")
    slug = post_data.get("slug", "")
    tags = post_data.get("tags", [])
    t_text = (title + " " + slug + " " + " ".join(tags)).lower()

    if any(k in t_text for k in ["무릎", "관절", "연골", "인공관절", "통증", "퇴행성"]):
        return "knee_joint"
    if any(k in t_text for k in ["임플란트", "틀니", "치과", "치아", "잇몸"]):
        return "implant_dental"
    if any(k in t_text for k in ["기초연금", "소득인정액", "기초노령", "단독가구", "부부가구"]):
        return "basic_pension"
    if any(k in t_text for k in ["국민연금", "조기수령", "연기수령", "손익분기점", "조기노령"]):
        return "pension_timeline"
    if any(k in t_text for k in ["건강보험", "피부양자", "건보료", "지역가입자"]):
        return "health_insurance"
    if any(k in t_text for k in ["65세", "혜택", "교통카드", "감면", "경로우대"]):
        return "senior_welfare_65"
    if any(k in t_text for k in ["상속", "증여", "취득세", "절세", "합산과세"]):
        return "inheritance_gift"
    if any(k in t_text for k in ["백내장", "노안", "안과", "녹내장", "황반변성", "개안수술"]):
        return "cataract_eye"
    if any(k in t_text for k in ["당뇨", "고혈압", "영양제", "음식 궁합", "만성질환", "혈압"]):
        return "chronic_care"
    if any(k in t_text for k in ["치매", "치매안심센터", "자가진단", "알츠하이머", "기억력"]):
        return "dementia_care"
    if any(k in t_text for k in ["대상포진", "예방접종", "백신", "폐렴구균", "독감"]):
        return "vaccine_immunity"
    if any(k in t_text for k in ["노인일자리", "일자리", "공공형", "사회서비스형", "시니어인턴"]):
        return "senior_jobs"
    if any(k in t_text for k in ["주택연금", "역모기지", "종신연금", "담보"]):
        return "housing_pension"
    if any(k in t_text for k in ["장기요양", "요양등급", "방문요양", "간병", "요양병원"]):
        return "longterm_care"
    if any(k in t_text for k in ["보청기", "난청", "청력", "이비인후과"]):
        return "hearing_aid"
    if any(k in t_text for k in ["실버타운", "고령자복지주택", "노인복지주택", "입주비용"]):
        return "housing_welfare"
    if any(k in t_text for k in ["에너지바우처", "난방비", "전기요금", "가스비"]):
        return "energy_voucher"
    if any(k in t_text for k in ["파크골프", "게이트볼", "시니어운동"]):
        return "park_golf"
    if any(k in t_text for k in ["불면증", "수면", "수면제", "수면 위생", "숙면"]):
        return "sleep_health"

    cat = post_data.get("category", "")
    if "건강" in cat:
        return "chronic_care"
    elif "연금" in cat or "절세" in cat:
        return "basic_pension"
    return "senior_welfare_65"

def get_theme_artwork(theme: str) -> str:
    """우측 500x500 영역(중심 x=940, y=315)에 렌더링되는 고품질 벡터 일러스트"""
    
    if theme == "knee_joint":
        return """
        <g transform="translate(940, 315)">
            <circle cx="0" cy="0" r="190" fill="#047857" opacity="0.25" filter="url(#glowFilter)"/>
            <circle cx="0" cy="0" r="175" fill="#0f172a" stroke="#34d399" stroke-width="3" stroke-dasharray="6,4" opacity="0.8"/>
            <circle cx="0" cy="0" r="150" fill="url(#panelGrad)" stroke="#10b981" stroke-width="2"/>
            <path d="M-45 -110 C-45 -60 -70 -25 -55 0 C-40 20 -20 15 0 20 C20 15 40 20 55 0 C70 -25 45 -60 45 -110 Z" fill="#e2e8f0" stroke="#94a3b8" stroke-width="3"/>
            <path d="M-50 -10 C-45 15 -15 28 0 28 C15 28 45 15 50 -10 C35 5 0 8 -50 -10 Z" fill="url(#goldGrad)" stroke="#fbbf24" stroke-width="2.5"/>
            <rect x="-42" y="32" width="84" height="12" rx="6" fill="#38bdf8" stroke="#0284c7" stroke-width="2"/>
            <path d="M-48 46 L48 46 L35 62 L-35 62 Z" fill="url(#goldGrad)" stroke="#f59e0b" stroke-width="2"/>
            <rect x="-8" y="62" width="16" height="45" rx="3" fill="#cbd5e1" stroke="#64748b" stroke-width="2"/>
            <path d="M-45 65 C-55 90 -35 120 -35 120 L35 120 C35 120 55 90 45 65 Z" fill="#e2e8f0" stroke="#94a3b8" stroke-width="3" opacity="0.85"/>
            <g transform="translate(90, -80)">
                <circle cx="0" cy="0" r="38" fill="#059669" stroke="#6ee7b7" stroke-width="3"/>
                <rect x="-7" y="-22" width="14" height="44" rx="3" fill="#ffffff"/>
                <rect x="-22" y="-7" width="44" height="14" rx="3" fill="#ffffff"/>
            </g>
            <g transform="translate(-85, 90)">
                <rect x="-35" y="-18" width="120" height="36" rx="18" fill="#1e293b" stroke="#fbbf24" stroke-width="2.5"/>
                <text x="25" y="6" font-family="'Pretendard', sans-serif" font-size="14" font-weight="900" fill="#fde68a" text-anchor="middle">수술비 240만원</text>
            </g>
        </g>
        """
    elif theme == "implant_dental":
        return """
        <g transform="translate(940, 315)">
            <circle cx="0" cy="0" r="190" fill="#0284c7" opacity="0.25" filter="url(#glowFilter)"/>
            <circle cx="0" cy="0" r="175" fill="#0f172a" stroke="#38bdf8" stroke-width="3" stroke-dasharray="6,4" opacity="0.8"/>
            <circle cx="0" cy="0" r="150" fill="url(#panelGrad)" stroke="#0ea5e9" stroke-width="2"/>
            <path d="M-90 10 Q0 -15 90 10" fill="none" stroke="#f43f5e" stroke-width="5" opacity="0.6"/>
            <path d="M-45 -10 C-45 -65 -30 -105 0 -105 C30 -105 45 -65 45 -10 C35 5 15 8 0 8 C-15 8 -35 5 -45 -10 Z" fill="#f8fafc" stroke="#94a3b8" stroke-width="3"/>
            <path d="M-25 -90 C-10 -95 10 -95 25 -90 C15 -45 10 0 0 0 C-10 0 -15 -45 -25 -90 Z" fill="#e2e8f0" opacity="0.5"/>
            <path d="M-22 8 L22 8 L16 32 L-16 32 Z" fill="url(#goldGrad)" stroke="#f59e0b" stroke-width="2"/>
            <path d="M-20 32 L20 32 L15 110 L0 125 L-15 110 Z" fill="#64748b" stroke="#334155" stroke-width="2"/>
            <line x1="-22" y1="45" x2="22" y2="40" stroke="#f8fafc" stroke-width="2.5"/>
            <line x1="-21" y1="58" x2="21" y2="53" stroke="#f8fafc" stroke-width="2.5"/>
            <line x1="-19" y1="71" x2="19" y2="66" stroke="#f8fafc" stroke-width="2.5"/>
            <line x1="-18" y1="84" x2="18" y2="79" stroke="#f8fafc" stroke-width="2.5"/>
            <line x1="-16" y1="97" x2="16" y2="92" stroke="#f8fafc" stroke-width="2.5"/>
            <g transform="translate(85, -60)">
                <circle cx="0" cy="0" r="42" fill="#0f172a" stroke="#fbbf24" stroke-width="3"/>
                <path d="M0 -36 A36 36 0 0 1 34 12 L0 0 Z" fill="url(#goldGrad)"/>
                <text x="0" y="7" font-family="'Pretendard', sans-serif" font-size="16" font-weight="900" fill="#ffffff" text-anchor="middle">30%</text>
                <text x="0" y="24" font-family="'Pretendard', sans-serif" font-size="10" font-weight="700" fill="#fde68a" text-anchor="middle">본인부담</text>
            </g>
            <g transform="translate(-80, 80)">
                <rect x="-35" y="-18" width="110" height="36" rx="18" fill="#1e293b" stroke="#38bdf8" stroke-width="2"/>
                <text x="20" y="6" font-family="'Pretendard', sans-serif" font-size="13" font-weight="900" fill="#38bdf8" text-anchor="middle">평생 2개 보장</text>
            </g>
        </g>
        """
    elif theme == "pension_timeline":
        return """
        <g transform="translate(940, 315)">
            <circle cx="0" cy="0" r="190" fill="#f59e0b" opacity="0.2" filter="url(#glowFilter)"/>
            <circle cx="0" cy="0" r="175" fill="#0f172a" stroke="#fbbf24" stroke-width="3" stroke-dasharray="6,4" opacity="0.8"/>
            <circle cx="0" cy="0" r="150" fill="url(#panelGrad)" stroke="#d97706" stroke-width="2"/>
            <line x1="-120" y1="50" x2="120" y2="50" stroke="#64748b" stroke-width="3"/>
            <circle cx="-80" cy="50" r="6" fill="#38bdf8" stroke="#ffffff" stroke-width="2"/>
            <text x="-80" y="75" font-family="'Pretendard', sans-serif" font-size="13" font-weight="700" fill="#94a3b8" text-anchor="middle">60세</text>
            <circle cx="0" cy="50" r="7" fill="#fbbf24" stroke="#ffffff" stroke-width="2"/>
            <text x="0" y="75" font-family="'Pretendard', sans-serif" font-size="14" font-weight="900" fill="#fbbf24" text-anchor="middle">65세</text>
            <circle cx="80" cy="50" r="6" fill="#34d399" stroke="#ffffff" stroke-width="2"/>
            <text x="80" y="75" font-family="'Pretendard', sans-serif" font-size="13" font-weight="700" fill="#94a3b8" text-anchor="middle">70세</text>
            <path d="M-80 50 Q-10 -10 110 -40" fill="none" stroke="#38bdf8" stroke-width="4"/>
            <path d="M0 50 Q40 10 110 -110" fill="none" stroke="#fbbf24" stroke-width="4"/>
            <g transform="translate(65, -28)">
                <circle cx="0" cy="0" r="12" fill="#ef4444" opacity="0.3" filter="url(#glowFilter)"/>
                <circle cx="0" cy="0" r="7" fill="#ef4444" stroke="#ffffff" stroke-width="2"/>
                <text x="0" y="-14" font-family="'Pretendard', sans-serif" font-size="12" font-weight="900" fill="#fca5a5" text-anchor="middle">손익분기점</text>
            </g>
            <g transform="translate(-50, -60)">
                <rect x="-35" y="-25" width="70" height="50" rx="8" fill="#1e3a8a" stroke="#60a5fa" stroke-width="2"/>
                <line x1="-35" y1="-5" x2="35" y2="-5" stroke="#93c5fd" stroke-width="2"/>
                <circle cx="0" cy="-14" r="7" fill="#fbbf24"/>
                <text x="0" y="14" font-family="'Pretendard', sans-serif" font-size="10" font-weight="900" fill="#ffffff" text-anchor="middle">국민연금</text>
            </g>
            <g transform="translate(60, 110)">
                <rect x="-45" y="-14" width="90" height="28" rx="14" fill="#451a03" stroke="#f59e0b" stroke-width="2"/>
                <text x="0" y="5" font-family="'Pretendard', sans-serif" font-size="12" font-weight="900" fill="#fde68a" text-anchor="middle">최대 -30% 감액</text>
            </g>
        </g>
        """
    elif theme == "basic_pension":
        return """
        <g transform="translate(940, 315)">
            <circle cx="0" cy="0" r="190" fill="#059669" opacity="0.25" filter="url(#glowFilter)"/>
            <circle cx="0" cy="0" r="175" fill="#0f172a" stroke="#10b981" stroke-width="3" stroke-dasharray="6,4" opacity="0.8"/>
            <circle cx="0" cy="0" r="150" fill="url(#panelGrad)" stroke="#34d399" stroke-width="2"/>
            <!-- 저울 양팔 -->
            <path d="M0 -70 L0 80" stroke="#94a3b8" stroke-width="6" stroke-linecap="round"/>
            <circle cx="0" cy="-70" r="8" fill="url(#goldGrad)"/>
            <line x1="-90" y1="-45" x2="90" y2="-25" stroke="#f59e0b" stroke-width="5" stroke-linecap="round"/>
            <!-- 좌측 소득평가액 접시 -->
            <path d="M-90 -45 L-115 15 L-65 15 Z" fill="#1e293b" stroke="#38bdf8" stroke-width="2"/>
            <text x="-90" y="8" font-family="'Pretendard', sans-serif" font-size="11" font-weight="800" fill="#bae6fd" text-anchor="middle">소득평가액</text>
            <!-- 우측 재산환산액 접시 -->
            <path d="M90 -25 L65 35 L115 35 Z" fill="#1e293b" stroke="#fbbf24" stroke-width="2"/>
            <text x="90" y="28" font-family="'Pretendard', sans-serif" font-size="11" font-weight="800" fill="#fef08a" text-anchor="middle">재산환산액</text>
            <!-- 하단 33.4만원 지급 배지 -->
            <g transform="translate(0, 95)">
                <rect x="-70" y="-18" width="140" height="36" rx="18" fill="#064e3b" stroke="#34d399" stroke-width="2.5"/>
                <text x="0" y="6" font-family="'Pretendard', sans-serif" font-size="15" font-weight="900" fill="#a7f3d0" text-anchor="middle">월 최대 33.4만 원</text>
            </g>
        </g>
        """
    else:
        # 범용 고품질 시니어 복지/건강 아트워크
        return f"""
        <g transform="translate(940, 315)">
            <circle cx="0" cy="0" r="190" fill="#047857" opacity="0.2" filter="url(#glowFilter)"/>
            <circle cx="0" cy="0" r="175" fill="#0f172a" stroke="#fbbf24" stroke-width="3" stroke-dasharray="6,4" opacity="0.8"/>
            <circle cx="0" cy="0" r="150" fill="url(#panelGrad)" stroke="#10b981" stroke-width="2"/>
            <rect x="-80" y="-70" width="160" height="140" rx="16" fill="#1e293b" stroke="#fbbf24" stroke-width="2"/>
            <path d="M-60 -30 L-20 -30 M-60 -5 L30 -5 M-60 20 L50 20" stroke="#94a3b8" stroke-width="4" stroke-linecap="round"/>
            <circle cx="45" cy="-30" r="14" fill="url(#goldGrad)"/>
            <path d="M40 -30 L44 -26 L51 -34" stroke="#1c1917" stroke-width="2.5" stroke-linecap="round" fill="none"/>
            <g transform="translate(0, 95)">
                <rect x="-70" y="-18" width="140" height="36" rx="18" fill="#1e293b" stroke="#34d399" stroke-width="2"/>
                <text x="0" y="6" font-family="'Pretendard', sans-serif" font-size="14" font-weight="900" fill="#fde68a" text-anchor="middle">2026 핵심 복지</text>
            </g>
        </g>
        """

def generate_svg_thumbnail(post_data: Dict[str, Any]) -> str:
    title = post_data.get("title", "")
    category = post_data.get("category", "시니어 건강 & 일상")
    desc = post_data.get("description", "6070 시니어 전문 복지·연금·건강 솔루션")
    cfg = CATEGORY_CONFIG.get(category, CATEGORY_CONFIG["시니어 건강 & 일상"])
    
    theme = classify_post(post_data)
    artwork_svg = get_theme_artwork(theme)

    lines = split_title(title, max_len=17)
    title_tspans = ""
    y_positions = [0, 58, 116]
    for i, line in enumerate(lines[:3]):
        y = y_positions[i]
        title_tspans += f'<tspan x="90" dy="{y if i == 0 else 58}">{escape_xml(line)}</tspan>\n    '

    clean_desc = escape_xml(desc[:42] + ("..." if len(desc) > 42 else ""))

    svg = f"""<svg width="1200" height="630" viewBox="0 0 1200 630" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="mainBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="{cfg['bg_stops'][0][1]}" stop-color="{cfg['bg_stops'][0][0]}" />
      <stop offset="{cfg['bg_stops'][1][1]}" stop-color="{cfg['bg_stops'][1][0]}" />
      <stop offset="{cfg['bg_stops'][2][1]}" stop-color="{cfg['bg_stops'][2][0]}" />
    </linearGradient>

    <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#f59e0b" />
      <stop offset="50%" stop-color="#fbbf24" />
      <stop offset="100%" stop-color="#fef08a" />
    </linearGradient>

    <linearGradient id="panelGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e293b" stop-opacity="0.95" />
      <stop offset="100%" stop-color="#0f172a" stop-opacity="0.98" />
    </linearGradient>

    <filter id="glowFilter" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="40" result="blur" />
    </filter>

    <filter id="dropShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#000000" flood-opacity="0.5" />
    </filter>
  </defs>

  <!-- 1. 배경 메인 -->
  <rect width="1200" height="630" fill="url(#mainBg)" />

  <!-- 2. 장식용 앰비언트 라이트 (글로우 효과) -->
  <circle cx="150" cy="120" r="280" fill="{cfg['accent']}" opacity="0.12" filter="url(#glowFilter)" />
  <circle cx="1050" cy="480" r="320" fill="{cfg['accent']}" opacity="0.15" filter="url(#glowFilter)" />

  <!-- 3. 외곽 프리미엄 골드 프레임 테두리 -->
  <rect x="36" y="36" width="1128" height="558" rx="28" fill="none" stroke="#fbbf24" stroke-opacity="0.25" stroke-width="1.5" />
  <rect x="44" y="44" width="1112" height="542" rx="22" fill="none" stroke="#ffffff" stroke-opacity="0.06" stroke-width="1" />

  <!-- 4. 좌측 상단 브랜드 헤더 -->
  <g transform="translate(90, 85)">
    <rect x="0" y="0" width="46" height="46" rx="12" fill="url(#goldGrad)" filter="url(#dropShadow)" />
    <path d="M12 32 L15 17 L23 25 L31 17 L34 32 Z" fill="#1c1917" />
    
    <text x="62" y="24" font-family="'Pretendard', sans-serif" font-size="22" font-weight="900" fill="#ffffff" letter-spacing="-0.5">골든라이프</text>
    <text x="168" y="24" font-family="'Pretendard', sans-serif" font-size="15" font-weight="700" fill="#fbbf24" letter-spacing="-0.2">GoldenLife</text>
    <text x="62" y="42" font-family="'Pretendard', sans-serif" font-size="13" font-weight="500" fill="#94a3b8">6070 시니어 복지·연금·건강 백과</text>
  </g>

  <!-- 5. 카테고리 태그 & 2026 개정판 뱃지 -->
  <g transform="translate(90, 160)">
    <rect x="0" y="0" width="{len(category) * 16 + 36}" height="38" rx="19" fill="{cfg['pill_bg']}" stroke="{cfg['pill_border']}" stroke-width="2" />
    <text x="18" y="24" font-family="'Pretendard', sans-serif" font-size="15" font-weight="800" fill="{cfg['pill_text']}">{escape_xml(category)}</text>

    <g transform="translate({len(category) * 16 + 48}, 0)">
      <rect x="0" y="0" width="165" height="38" rx="19" fill="#1e293b" stroke="#f59e0b" stroke-width="1.5" />
      <text x="16" y="24" font-family="'Pretendard', sans-serif" font-size="14" font-weight="800" fill="#fde68a">★ {cfg['badge']}</text>
    </g>
  </g>

  <!-- 6. 메인 타이틀 (좌측 영역) -->
  <text x="90" y="260" font-family="'Pretendard', sans-serif" font-size="46" font-weight="900" fill="#ffffff" letter-spacing="-1.5" filter="url(#dropShadow)">
    {title_tspans}
  </text>

  <!-- 7. 핵심 요약 서브카피 박스 -->
  <g transform="translate(90, 465)">
    <rect x="0" y="0" width="580" height="54" rx="14" fill="#0f172a" fill-opacity="0.8" stroke="#ffffff" stroke-opacity="0.12" stroke-width="1" />
    <rect x="0" y="0" width="6" height="54" rx="3" fill="url(#goldGrad)" />
    <text x="24" y="33" font-family="'Pretendard', sans-serif" font-size="17" font-weight="500" fill="#e2e8f0">{clean_desc}</text>
  </g>

  <!-- 8. 하단 푸터 인포 -->
  <g transform="translate(90, 555)">
    <circle cx="6" cy="-5" r="4" fill="#10b981" />
    <text x="18" y="0" font-family="'Pretendard', sans-serif" font-size="15" font-weight="700" fill="#fde68a">공식 정보 검증 완료</text>
    <text x="170" y="0" font-family="'Pretendard', sans-serif" font-size="14" font-weight="400" fill="#94a3b8">• goldianpark.github.io</text>
  </g>

  <!-- 9. 우측 전용 맞춤형 테마 일러스트레이션 아트워크 -->
  {artwork_svg}
</svg>
"""
    return svg.strip()

def generate_thumbnail_for_post(post_data: Dict[str, Any], output_dir: Optional[Path] = None) -> str:
    slug = post_data.get("slug", "")
    if not slug:
        raise ValueError("포스트 데이터에 slug가 반드시 필요합니다.")

    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{slug}.svg"

    svg_content = generate_svg_thumbnail(post_data)
    out_file.write_text(svg_content, encoding="utf-8")

    # dist 디렉토리에도 동기화 복사
    dist_file = DEFAULT_DIST_DIR / f"{slug}.svg"
    try:
        dist_file.parent.mkdir(parents=True, exist_ok=True)
        dist_file.write_text(svg_content, encoding="utf-8")
    except Exception:
        pass

    return f"/images/thumbnails/{slug}.svg"

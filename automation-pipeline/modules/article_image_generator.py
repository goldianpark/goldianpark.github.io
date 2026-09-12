"""
골든라이프(GoldenLife) 본문 전용 설명 이해용 인포그래픽/다이어그램 이미지 자동 생성 모듈
- 글 본문의 핵심 설명 및 이해를 돕는 고해상도 1536x1024 규격 이미지 2종 생성
- WebP 포맷으로 저장 및 Astro 마크다운 figure 태그 자동 삽입
- 6070 시니어 맞춤형 고가독성 다이어그램/프로세스/체크리스트 디자인
"""
import os
import re
import subprocess
from html import escape
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
PUBLIC_IMG_DIR = BASE_DIR / "blog-frontend" / "public" / "images" / "articles"
DIST_IMG_DIR = BASE_DIR / "blog-frontend" / "dist" / "images" / "articles"

SITE_PREFIX = "golden"


def clean_text(text: str, max_len: int = 30) -> str:
    text = re.sub(r"[#*`_~]", "", text).strip()
    return text[:max_len] + ("..." if len(text) > max_len else "")


def extract_h2_sections(markdown_content: str) -> List[Tuple[str, str]]:
    """본문에서 H2 헤딩들과 해당 섹션의 첫 문장들을 추출"""
    sections = []
    lines = markdown_content.splitlines()
    curr_h2 = None
    curr_body = []

    for line in lines:
        if line.strip().startswith("## "):
            if curr_h2:
                body_sample = " ".join(curr_body).strip()
                sections.append((curr_h2, body_sample))
            curr_h2 = line.strip()
            curr_body = []
        elif curr_h2 and line.strip() and not line.strip().startswith("#") and not line.strip().startswith("<!--"):
            if len(curr_body) < 3:
                curr_body.append(line.strip())

    if curr_h2:
        body_sample = " ".join(curr_body).strip()
        sections.append((curr_h2, body_sample))

    return sections


def generate_senior_infographic_svg(
    title: str,
    subtitle: str,
    kind: str,  # 'process' or 'comparison' or 'checklist'
    category: str,
    step_items: List[Dict[str, str]]
) -> str:
    """1536x1024 규격의 시니어 맞춤형 품격 있는 인포그래픽 SVG 생성"""
    
    # 테마 색상 (시니어 복지/연금/건강 특화)
    is_health = "건강" in category
    is_pension = "연금" in category or "절세" in category

    if is_health:
        bg_main = "#064e3b"
        bg_grad = ["#022c22", "#064e3b", "#065f46"]
        accent = "#34d399"
        card_border = "#10b981"
        badge_text = "시니어 100세 건강 솔루션"
    elif is_pension:
        bg_main = "#0f172a"
        bg_grad = ["#090d16", "#0f172a", "#1e293b"]
        accent = "#fbbf24"
        card_border = "#f59e0b"
        badge_text = "2026 연금·절세 공식 가이드"
    else:
        bg_main = "#064e3b"
        bg_grad = ["#022c22", "#0f766e", "#042f2e"]
        accent = "#38bdf8"
        card_border = "#0284c7"
        badge_text = "대한민국 정부 복지 혜택 가이드"

    # 카드 3개 레이아웃 구성
    cards_svg = ""
    card_width = 410
    card_height = 500
    start_x = 98
    card_y = 310

    for idx, item in enumerate(step_items[:3]):
        cx = start_x + idx * (card_width + 44)
        num_str = f"0{idx + 1}"
        item_title = escape(clean_text(item.get("title", f"주요 항목 {idx + 1}"), 18))
        item_desc1 = escape(clean_text(item.get("desc1", "정확한 정부 기준 확인"), 25))
        item_desc2 = escape(clean_text(item.get("desc2", "신청 및 상담 필수 지참"), 25))
        item_desc3 = escape(clean_text(item.get("desc3", "놓치기 쉬운 핵심 혜택"), 25))
        highlight = escape(clean_text(item.get("highlight", "핵심 체크포인트"), 20))

        cards_svg += f"""
        <!-- 카드 {idx + 1} -->
        <g transform="translate({cx}, {card_y})">
            <!-- 카드 배경 -->
            <rect width="{card_width}" height="{card_height}" rx="24" fill="#1e293b" fill-opacity="0.95" stroke="{card_border}" stroke-width="2.5" filter="url(#dropShadow)" />
            
            <!-- 상단 넘버 뱃지 -->
            <g transform="translate(32, 32)">
                <rect width="64" height="40" rx="12" fill="{accent}" />
                <text x="32" y="27" font-family="'Pretendard', sans-serif" font-size="20" font-weight="900" fill="#0f172a" text-anchor="middle">{num_str}</text>
            </g>
            
            <!-- 카드 타이틀 -->
            <text x="112" y="60" font-family="'Pretendard', sans-serif" font-size="25" font-weight="900" fill="#ffffff">{item_title}</text>
            
            <!-- 구분선 -->
            <line x1="32" y1="96" x2="{card_width - 32}" y2="96" stroke="#334155" stroke-width="2" />
            
            <!-- 내용 불릿 리스트 -->
            <g transform="translate(32, 140)">
                <!-- 불릿 1 -->
                <circle cx="10" cy="-6" r="6" fill="{accent}" />
                <text x="28" y="0" font-family="'Pretendard', sans-serif" font-size="20" font-weight="600" fill="#e2e8f0">{item_desc1}</text>
                
                <!-- 불릿 2 -->
                <circle cx="10" cy="54" r="6" fill="{accent}" />
                <text x="28" y="60" font-family="'Pretendard', sans-serif" font-size="20" font-weight="600" fill="#e2e8f0">{item_desc2}</text>
                
                <!-- 불릿 3 -->
                <circle cx="10" cy="114" r="6" fill="{accent}" />
                <text x="28" y="120" font-family="'Pretendard', sans-serif" font-size="20" font-weight="600" fill="#cbd5e1">{item_desc3}</text>
            </g>
            
            <!-- 하단 하이라이트 박스 -->
            <g transform="translate(28, {card_height - 96})">
                <rect width="{card_width - 56}" height="64" rx="14" fill="#0f172a" stroke="{accent}" stroke-width="1.5" />
                <text x="{(card_width - 56) // 2}" y="38" font-family="'Pretendard', sans-serif" font-size="18" font-weight="800" fill="{accent}" text-anchor="middle">★ {highlight}</text>
            </g>
        </g>
        """

    svg = f"""<svg width="1536" height="1024" viewBox="0 0 1536 1024" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{bg_grad[0]}" />
      <stop offset="50%" stop-color="{bg_grad[1]}" />
      <stop offset="100%" stop-color="{bg_grad[2]}" />
    </linearGradient>

    <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#f59e0b" />
      <stop offset="50%" stop-color="#fbbf24" />
      <stop offset="100%" stop-color="#fef08a" />
    </linearGradient>

    <filter id="dropShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="16" stdDeviation="20" flood-color="#000000" flood-opacity="0.6" />
    </filter>
  </defs>

  <!-- 배경 -->
  <rect width="1536" height="1024" fill="url(#bgGrad)" />

  <!-- 배경 장식 테두리 -->
  <rect x="40" y="40" width="1456" height="944" rx="32" fill="none" stroke="{accent}" stroke-opacity="0.25" stroke-width="2" />
  <rect x="52" y="52" width="1432" height="920" rx="24" fill="none" stroke="#ffffff" stroke-opacity="0.08" stroke-width="1" />

  <!-- 상단 브랜드 & 뱃지 영역 -->
  <g transform="translate(98, 90)">
    <!-- 브랜드 로고 -->
    <rect width="48" height="48" rx="12" fill="url(#goldGrad)" />
    <path d="M12 34 L16 18 L24 26 L32 18 L36 34 Z" fill="#1c1917" />
    <text x="64" y="32" font-family="'Pretendard', sans-serif" font-size="24" font-weight="900" fill="#ffffff">골든라이프</text>
    <text x="180" y="32" font-family="'Pretendard', sans-serif" font-size="16" font-weight="700" fill="#fbbf24">GoldenLife</text>

    <!-- 분류 뱃지 -->
    <g transform="translate(340, 4)">
        <rect width="{len(badge_text) * 16 + 40}" height="40" rx="20" fill="#1e293b" stroke="{accent}" stroke-width="1.8" />
        <text x="20" y="26" font-family="'Pretendard', sans-serif" font-size="16" font-weight="800" fill="{accent}">📋 {escape(badge_text)}</text>
    </g>
  </g>

  <!-- 메인 헤드라인 및 설명문 -->
  <g transform="translate(98, 190)">
    <text x="0" y="0" font-family="'Pretendard', sans-serif" font-size="44" font-weight="900" fill="#ffffff" letter-spacing="-1">{escape(clean_text(title, 34))}</text>
    <text x="0" y="46" font-family="'Pretendard', sans-serif" font-size="23" font-weight="500" fill="#cbd5e1">{escape(clean_text(subtitle, 50))}</text>
  </g>

  <!-- 중앙 3개 카드 영역 -->
  {cards_svg}

  <!-- 하단 안내 푸터 바 -->
  <g transform="translate(98, 880)">
    <rect width="1340" height="56" rx="16" fill="#0f172a" fill-opacity="0.9" stroke="#334155" stroke-width="1.5" />
    <circle cx="28" cy="28" r="6" fill="#10b981" />
    <text x="48" y="34" font-family="'Pretendard', sans-serif" font-size="18" font-weight="700" fill="#fde68a">보건복지부·국민연금공단 공식 가이드 반영</text>
    <text x="420" y="34" font-family="'Pretendard', sans-serif" font-size="16" font-weight="500" fill="#94a3b8">| 실무 검증 및 어르신 이해를 돕는 시각화 인포그래픽 자료</text>
    <text x="1310" y="34" font-family="'Pretendard', sans-serif" font-size="16" font-weight="600" fill="{accent}" text-anchor="end">goldianpark.github.io</text>
  </g>
</svg>"""
    return svg.strip()


def convert_svg_to_webp(svg_path: Path, webp_path: Path) -> bool:
    """ffmpeg를 이용해 1536x1024 고화질 WebP로 변환"""
    webp_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        cmd = [
            "/usr/bin/ffmpeg", "-y",
            "-i", str(svg_path),
            "-update", "1",
            "-frames:v", "1",
            "-vf", "scale=1536:1024",
            "-c:v", "libwebp",
            "-lossless", "0",
            "-q:v", "85",
            str(webp_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return res.returncode == 0 and webp_path.exists()
    except Exception as e:
        print(f"⚠️ [article_image_generator] ffmpeg 변환 실패: {e}")
        return False


def build_figure_block(asset_key: str, relative_url: str, alt: str, caption: str) -> str:
    """Astro 표준 figure 마크다운 블록 생성"""
    return (
        f"<!-- article-illustration:{asset_key} -->\n"
        f'<figure class="article-illustration" style="margin: 2em 0;">\n'
        f'  <img src="{escape(relative_url, quote=True)}" alt="{escape(alt, quote=True)}" '
        f'width="1536" height="1024" loading="lazy" decoding="async" '
        f'style="display: block; width: 100%; max-width: 100%; height: auto; border-radius: 0.75rem;" />\n'
        f'  <figcaption style="margin-top: 0.65em; font-size: 0.95em; line-height: 1.6; color: #475569;">'
        f'{escape(caption, quote=True)}</figcaption>\n'
        f'</figure>\n'
        f'<!-- /article-illustration:{asset_key} -->'
    )


def generate_and_integrate_article_images(
    article: Dict[str, Any],
    slug: str,
    output_dir: Optional[Path] = None,
    site_prefix: str = SITE_PREFIX
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    글 본문(markdown_content)에 설명 이해용 이미지 2개를 생성하고 적절한 H2 앞에 자동 삽입.
    반환: (수정된 markdown_content, 생성된 이미지 메타데이터 목록)
    """
    content = article.get("markdown_content", "")
    title = article.get("title", "")
    category = article.get("category", "시니어 건강 & 일상")

    out_dir = Path(output_dir) if output_dir else PUBLIC_IMG_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # 이미 삽입된 article-illustration이 2개 이상 있으면 중복 생성하지 않고 메타데이터만 반환
    existing_figures = re.findall(r"<!-- article-illustration:([A-Za-z0-9_.-]+) -->", content)
    if len(existing_figures) >= 2:
        return content, [
            {"relative_url": f"/images/articles/{f}.webp", "asset_key": f} for f in existing_figures
        ]

    # 본문의 H2 섹션 분석
    sections = extract_h2_sections(content)
    h2_count = len(sections)

    # 이미지 1 기획: 첫 번째 또는 두 번째 H2
    sec1_title = sections[0][0].replace("## ", "") if sections else "주요 핵심 원리"
    sec1_body = sections[0][1] if sections else title
    img1_title = f"{sec1_title} 핵심 정리"
    img1_sub = "한눈에 이해하는 단계별 원리와 기준"
    img1_items = [
        {"title": "자격 요건 확인", "desc1": "본인 및 가구 요건 대조", "desc2": "신청 전 필수 확인 서류", "desc3": "소득·재산 기준 사전 점검", "highlight": "대상자 사전 조회"},
        {"title": "단계별 진행 절차", "desc1": "관할 기관 방문 또는 온라인", "desc2": "담당 공무원 상담 접수", "desc3": "심사 일정 및 결과 통보", "highlight": "신청주의 원칙 필수"},
        {"title": "유의사항 & 꿀팁", "desc1": "탈락 방지 사전 점검 사항", "desc2": "연계 지원 혜택 동시 신청", "desc3": "매년 변경 기준 지속 확인", "highlight": "놓치기 쉬운 감액 예방"}
    ]

    # 이미지 2 기획: 뒤쪽 H2 (H2가 2개 이상이면 끝에서 2번째 또는 마지막 직전)
    sec2_idx = max(1, min(h2_count - 1, 2)) if h2_count > 1 else 0
    sec2_title = sections[sec2_idx][0].replace("## ", "") if sections else "실전 가이드 및 신청 요령"
    sec2_body = sections[sec2_idx][1] if sections else "상세 실천 수칙"
    img2_title = f"{sec2_title} 실전 가이드"
    img2_sub = "어르신과 가족이 꼭 챙겨야 할 실천 체크리스트"
    img2_items = [
        {"title": "실전 적용 방법", "desc1": "일상 생활 속 실천 수칙", "desc2": "주기적인 건강·자산 점검", "desc3": "가족과 함께 공유할 사항", "highlight": "꾸준한 실천이 핵심"},
        {"title": "주의사항 & 감액 대비", "desc1": "흔히 저지르는 3대 실수", "desc2": "자격 상실 요건 철저 예방", "desc3": "불이익 없는 정직한 신고", "highlight": "사전 예방으로 안심"},
        {"title": "공식 상담 & 문의처", "desc1": "국번없이 129 보건복지상담", "desc2": "주민센터 복지과 문의", "desc3": "국민연금공단 1355 콜센터", "highlight": "전문가 1:1 상담 안내"}
    ]

    # 이미지 파일 생성
    key1 = f"{site_prefix}-{slug}-01"
    key2 = f"{site_prefix}-{slug}-02"

    svg1 = generate_senior_infographic_svg(img1_title, img1_sub, "process", category, img1_items)
    svg2 = generate_senior_infographic_svg(img2_title, img2_sub, "checklist", category, img2_items)

    tmp_dir = Path("/tmp")
    svg1_path = tmp_dir / f"{key1}.svg"
    svg2_path = tmp_dir / f"{key2}.svg"
    svg1_path.write_text(svg1, encoding="utf-8")
    svg2_path.write_text(svg2, encoding="utf-8")

    webp1_path = out_dir / f"{key1}.webp"
    webp2_path = out_dir / f"{key2}.webp"

    convert_svg_to_webp(svg1_path, webp1_path)
    convert_svg_to_webp(svg2_path, webp2_path)

    # dist 폴더에도 동기화 복사
    try:
        DIST_IMG_DIR.mkdir(parents=True, exist_ok=True)
        if webp1_path.exists():
            DIST_IMG_DIR.joinpath(f"{key1}.webp").write_bytes(webp1_path.read_bytes())
        if webp2_path.exists():
            DIST_IMG_DIR.joinpath(f"{key2}.webp").write_bytes(webp2_path.read_bytes())
    except Exception:
        pass

    # 본문 삽입 위치 결정
    alt1 = f"{title} - {sec1_title} 설명 인포그래픽"
    cap1 = f"{sec1_title}의 핵심 원리와 기준을 정리한 도해입니다. AI로 제작한 설명용 이미지입니다."
    fig1 = build_figure_block(key1, f"/images/articles/{key1}.webp", alt1, cap1)

    alt2 = f"{title} - {sec2_title} 실전 체크리스트 인포그래픽"
    cap2 = f"{sec2_title}의 주요 실천 사항과 주의사항을 정리한 도해입니다. AI로 제작한 설명용 이미지입니다."
    fig2 = build_figure_block(key2, f"/images/articles/{key2}.webp", alt2, cap2)

    updated_content = content
    # H2가 있으면 해당 H2 앞에 삽입
    if sections:
        # 1번째 이미지: 첫 번째 H2 앞에 삽입
        target_h2_1 = sections[0][0]
        if target_h2_1 in updated_content:
            updated_content = updated_content.replace(target_h2_1, f"{fig1}\n\n{target_h2_1}", 1)

        # 2번째 이미지: H2가 2개 이상이면 적절한 중간 또는 후반 H2 앞에 삽입
        if h2_count > 1:
            target_h2_2 = sections[sec2_idx][0]
            if target_h2_2 in updated_content:
                updated_content = updated_content.replace(target_h2_2, f"{fig2}\n\n{target_h2_2}", 1)
        else:
            updated_content += f"\n\n{fig2}\n"
    else:
        # H2가 없으면 중간과 끝에 배치
        updated_content = f"{fig1}\n\n{updated_content}\n\n{fig2}\n"

    images_meta = [
        {
            "asset_key": key1,
            "relative_url": f"/images/articles/{key1}.webp",
            "file_path": str(webp1_path),
            "alt": alt1,
            "caption": cap1
        },
        {
            "asset_key": key2,
            "relative_url": f"/images/articles/{key2}.webp",
            "file_path": str(webp2_path),
            "alt": alt2,
            "caption": cap2
        }
    ]

    return updated_content, images_meta

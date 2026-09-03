import { getCollection } from 'astro:content';

export async function getStaticPaths() {
  const posts = await getCollection('blog', ({ data }) => !data.draft);
  return posts.map((post) => ({
    params: { slug: post.slug },
    props: { post },
  }));
}

export async function GET({ props }: any) {
  const { post } = props;
  const title = post.data.title || '골든라이프 블로그 포스팅';
  const category = post.data.category || '정부지원금 & 복지';
  const readingTime = post.data.readingTime || '5 min read';
  const pubDate = new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(post.data.pubDate);

  // 긴 제목 분할 (25자 단위 최대 3줄)
  const words = title.split(' ');
  const lines: string[] = [];
  let currentLine = '';

  for (const word of words) {
    if ((currentLine + ' ' + word).trim().length > 22) {
      if (currentLine) lines.push(currentLine.trim());
      currentLine = word;
    } else {
      currentLine = (currentLine + ' ' + word).trim();
    }
  }
  if (currentLine) lines.push(currentLine.trim());
  const displayLines = lines.slice(0, 3);

  // XML 특수문자 이스케이프
  const escapeXml = (unsafe: string) =>
    unsafe
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&apos;');

  const titleSvgText = displayLines
    .map((line, idx) => `<tspan x="80" dy="${idx === 0 ? 0 : 54}">${escapeXml(line)}</tspan>`)
    .join('');

  const svg = `
<svg width="1200" height="630" viewBox="0 0 1200 630" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1c160e" />
      <stop offset="50%" stop-color="#2a2014" />
      <stop offset="100%" stop-color="#120e09" />
    </linearGradient>
    <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#b8860b" />
      <stop offset="100%" stop-color="#fbbf24" />
    </linearGradient>
    <linearGradient id="cardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.08" />
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.02" />
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="1200" height="630" fill="url(#bgGrad)" />

  <!-- Ambient Glow (Warm Gold) -->
  <circle cx="1050" cy="150" r="350" fill="#d97706" opacity="0.25" filter="blur(80px)" />
  <circle cx="150" cy="500" r="300" fill="#f59e0b" opacity="0.18" filter="blur(70px)" />

  <!-- Inner Glass Card with subtle golden border -->
  <rect x="50" y="50" width="1100" height="530" rx="32" fill="url(#cardGrad)" stroke="#fef3c7" stroke-opacity="0.18" stroke-width="1.5" />

  <!-- Brand Header -->
  <g transform="translate(80, 100)">
    <rect x="0" y="0" width="40" height="40" rx="12" fill="url(#goldGrad)" />
    <text x="54" y="27" font-family="-apple-system, BlinkMacSystemFont, 'Pretendard', sans-serif" font-size="22" font-weight="900" fill="#ffffff" letter-spacing="-0.5">골든라이프 (GoldenLife)</text>
    <text x="310" y="27" font-family="-apple-system, BlinkMacSystemFont, 'Pretendard', sans-serif" font-size="16" fill="#fde68a">시니어 복지·연금·건강 백과</text>
  </g>

  <!-- Category & Read Time Badge -->
  <g transform="translate(80, 180)">
    <rect x="0" y="0" width="${escapeXml(category).length * 20 + 40}" height="38" rx="19" fill="#451a03" stroke="#f59e0b" stroke-width="1.5" />
    <text x="20" y="24" font-family="-apple-system, BlinkMacSystemFont, 'Pretendard', sans-serif" font-size="15" font-weight="700" fill="#fef3c7">${escapeXml(category)}</text>
    <text x="${escapeXml(category).length * 20 + 54}" y="24" font-family="-apple-system, BlinkMacSystemFont, 'Pretendard', sans-serif" font-size="15" fill="#fde68a">• ${escapeXml(readingTime)}</text>
  </g>

  <!-- Post Title -->
  <text x="80" y="300" font-family="-apple-system, BlinkMacSystemFont, 'Pretendard', sans-serif" font-size="44" font-weight="800" fill="#ffffff" letter-spacing="-1" line-height="1.3">
    ${titleSvgText}
  </text>

  <!-- Footer Info -->
  <g transform="translate(80, 520)">
    <text x="0" y="0" font-family="-apple-system, BlinkMacSystemFont, 'Pretendard', sans-serif" font-size="16" fill="#fef3c7" opacity="0.8">발행일: ${pubDate} | goldianpark.github.io</text>
    <text x="940" y="0" font-family="-apple-system, BlinkMacSystemFont, 'Pretendard', sans-serif" font-size="16" font-weight="bold" fill="#fbbf24" text-anchor="end">자세히 보러 가기 →</text>
  </g>
</svg>
`.trim();

  return new Response(svg, {
    headers: {
      'Content-Type': 'image/svg+xml; charset=utf-8',
      'Cache-Control': 'public, max-age=31536000, immutable',
    },
  });
}

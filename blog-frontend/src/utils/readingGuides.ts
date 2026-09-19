import type { CollectionEntry } from 'astro:content';

type BlogPost = CollectionEntry<'blog'>;

// Recommendation surfaces omit visible editing notes. Archives retain every published post.
export function isRecommendationEligible(post: BlogPost): boolean {
  return !post.data.draft && !/\[(?:💡|🔍)[^\]\n]*\]|^\s*TODO\s*:/m.test(post.body);
}

export const readingGuides = [
  {
    id: 'benefits',
    title: '복지 신청을 준비하고 싶어요',
    description: '신청 항목을 살펴본 뒤, 주거·치과 등 필요한 주제의 글로 이동하세요.',
    category: '정부지원금 & 복지',
    articles: [
      { slug: '2026-09-12-basic-pension-application-checklist', note: '신청 전에 확인할 항목을 정리할 때' },
      { slug: '2026-09-08-passive-income-3697', note: '주거 모집공고를 읽는 순서를 찾을 때' },
      { slug: '2026-09-04-2-30', note: '치과 상담에서 물어볼 항목을 정리할 때' },
    ],
  },
  {
    id: 'pension',
    title: '연금 상담과 비교를 준비하고 싶어요',
    description: '상담 질문을 먼저 정리하고, 비교 글에서 사용하는 가정과 계산 조건을 살펴보세요.',
    category: '연금 & 절세 상식',
    articles: [
      { slug: '2026-09-12-passive-income-4920', note: '조기수령 상담 전에 질문을 정리할 때' },
      { slug: '2026-09-12-vs', note: '수령 시점 비교 글의 가정을 읽어볼 때' },
    ],
  },
  {
    id: 'care',
    title: '진료 전 확인할 내용을 찾고 싶어요',
    description: '관심 있는 진료 주제를 골라 상담 전 메모와 확인 항목을 읽어보세요.',
    category: '시니어 건강 & 일상',
    articles: [
      { slug: '2026-09-12-2025-2026-120', note: '무릎 수술비 지원 상담의 확인 항목을 찾을 때' },
      { slug: '2026-09-10-passive-income-2084', note: '임플란트 재수술 비용 상담을 준비할 때' },
      { slug: '2026-09-08-passive-income-9290', note: '대상포진 관련 진료·접종 질문을 정리할 때' },
    ],
  },
  {
    id: 'daily',
    title: '일상 정보를 천천히 살펴보고 싶어요',
    description: '수면 습관 점검과 파크골프 이용 준비 중 지금 필요한 글을 골라보세요.',
    category: '시니어 건강 & 일상',
    articles: [
      { slug: '2026-09-11-7', note: '수면 습관과 진료 전 메모 항목을 읽을 때' },
      { slug: '2026-09-09-2026-100', note: '파크골프장 방문 전 확인할 내용을 찾을 때' },
    ],
  },
];

export function resolveReadingGuides(posts: BlogPost[]) {
  const available = new Map(posts.filter(isRecommendationEligible).map(post => [post.slug, post]));
  return readingGuides.map(guide => ({
    ...guide,
    articles: guide.articles.flatMap(article => {
      const post = available.get(article.slug);
      return post ? [{ ...article, post }] : [];
    }),
  })).filter(guide => guide.articles.length > 0);
}

const categoryDescriptions: Record<string, string> = {
  '정부지원금 & 복지': '복지 신청과 주거·의료비 관련 글을 모았습니다. 관심 있는 제도의 신청 항목과 공식 안내를 찾는 데 활용하세요.',
  '연금 & 절세 상식': '연금 수령 시점과 세금 관련 글을 모았습니다. 상담 질문을 정리하고 각 글의 비교 조건을 살펴보세요.',
  '시니어 건강 & 일상': '진료 전 확인할 내용과 일상생활 준비에 관한 글을 모았습니다. 지금 궁금한 주제로 이동해 읽어보세요.',
};

export function getCategoryDescription(category: string): string {
  return categoryDescriptions[category] || `${category}에 관한 글을 주제별로 살펴보세요.`;
}

export function getCategoryGuides(category: string) {
  return readingGuides.filter(guide => guide.category === category);
}

// A shared category alone is too broad: a pension article is not a knee-surgery recommendation.
const topics = [
  /기초연금/, /국민연금/, /임플란트|틀니/, /무릎|관절/, /주택연금/,
  /농지연금/, /복지주택|고령자\s*주택/, /백내장|안과|망막|황반/,
  /대상포진/, /장기요양|요양원|요양병원|간병|돌봄/, /증여|상속|차용증/,
  /수면|잠들/, /파크골프/, /일자리|재취업|알바/, /치매/, /폐렴구균/,
];

export function getRelatedPosts(posts: BlogPost[], current: BlogPost, limit = 3): BlogPost[] {
  const currentTopics = topics.filter(topic => topic.test(current.data.title));
  return posts.filter(post => post.slug !== current.slug && isRecommendationEligible(post))
    .map(post => {
      const sharedTopics = currentTopics.filter(topic => topic.test(post.data.title)).length;
      const sharedTags = new Set(post.data.tags.filter(tag => current.data.tags.includes(tag))).size;
      return {
        post,
        sharedTopics,
        score: sharedTopics * 12 + Math.min(sharedTags, 3) + (post.data.category === current.data.category ? 2 : 0),
      };
    })
    .filter(item => item.sharedTopics > 0)
    .sort((a, b) => b.score - a.score || b.post.data.pubDate.valueOf() - a.post.data.pubDate.valueOf())
    .slice(0, Math.max(0, limit))
    .map(item => item.post);
}

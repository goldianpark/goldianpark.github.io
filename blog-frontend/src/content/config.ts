import { defineCollection, z } from 'astro:content';

const blogCollection = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    heroImage: z.string().optional().default('/images/default-hero.svg'),
    category: z.string().default('정부지원금 & 복지'),
    tags: z.array(z.string()).default([]),
    author: z.string().default('골든라이프 편집팀'),
    readingTime: z.string().optional().default('5 min read'),
    featured: z.boolean().optional().default(false),
    draft: z.boolean().optional().default(false),
    faqs: z.array(
      z.object({
        question: z.string(),
        answer: z.string(),
      })
    ).optional(),
    summaryCards: z.array(
      z.object({
        badge: z.string(),
        title: z.string(),
        desc: z.string(),
        icon: z.string().optional(),
      })
    ).optional(),
  }),
});

export const collections = {
  blog: blogCollection,
};

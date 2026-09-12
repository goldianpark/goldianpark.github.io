import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import siteConfig from '../config/site';

export async function GET(context: any) {
  const posts = await getCollection('blog', ({ data }) => !data.draft);
  const sortedPosts = posts.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());

  return rss({
    title: siteConfig.site.name,
    description: siteConfig.site.description,
    site: context.site || siteConfig.site.url,
    items: sortedPosts.map((post) => ({
      title: post.data.title,
      pubDate: post.data.pubDate,
      description: post.data.description,
      link: `/blog/${post.slug}/`,
      categories: [post.data.category, ...(post.data.tags || [])],
    })),
    customData: `<language>ko-KR</language>`,
  });
}

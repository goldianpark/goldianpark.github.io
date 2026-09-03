import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://absianp.github.io/goldenlife-blog',
  base: '/goldenlife-blog',
  trailingSlash: 'always',
  build: {
    format: 'directory',
  },
  markdown: {
    syntaxHighlight: 'shiki',
    shikiConfig: {
      theme: 'github-dark',
      wrap: true,
    },
  },
});

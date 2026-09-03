import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://goldianpark.github.io',
  base: '/',
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

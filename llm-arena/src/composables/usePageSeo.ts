/** Per-route document title / description for SPA SEO & browser tab clarity. */

export type PageSeo = {
  title: string
  description: string
  path?: string
}

const SITE = 'LLM Arena'

export function applyPageSeo(seo: PageSeo) {
  const fullTitle = seo.title.includes(SITE) ? seo.title : `${seo.title} · ${SITE}`
  document.title = fullTitle

  upsertMeta('name', 'description', seo.description)
  upsertMeta('property', 'og:title', fullTitle)
  upsertMeta('property', 'og:description', seo.description)
  upsertMeta('name', 'twitter:title', fullTitle)
  upsertMeta('name', 'twitter:description', seo.description)

  if (seo.path) {
    const base = window.location.origin + (import.meta.env.BASE_URL || '/').replace(/\/?$/, '')
    const href = `${base}${seo.path.startsWith('/') ? seo.path : `/${seo.path}`}`
    let link = document.querySelector('link[rel="canonical"]') as HTMLLinkElement | null
    if (!link) {
      link = document.createElement('link')
      link.rel = 'canonical'
      document.head.appendChild(link)
    }
    // Keep GitHub as project canonical when still on localhost
    if (!/localhost|127\.0\.0\.1/.test(window.location.hostname)) {
      link.href = href
    }
  }
}

function upsertMeta(attr: 'name' | 'property', key: string, content: string) {
  let el = document.querySelector(`meta[${attr}="${key}"]`) as HTMLMetaElement | null
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.content = content
}

/** Default SEO map (zh); English titles applied when locale is en. */
export const ROUTE_SEO: Record<string, { zh: PageSeo; en: PageSeo }> = {
  home: {
    zh: {
      title: '首页',
      description:
        'LLM Arena 公平编程智能体竞技场：OpenCode 官方引擎，单一变量原则，多模型对战与 pytest 判分。',
      path: '/',
    },
    en: {
      title: 'Home',
      description:
        'LLM Arena — fair coding-agent benchmark with official OpenCode, single-variable matches, and pytest scoring.',
      path: '/',
    },
  },
  arena: {
    zh: {
      title: '竞技场',
      description: '多模型公平对战：冻结工具与约束，仅模型不同；实时 OpenCode 过程与页面预览。',
      path: '/arena',
    },
    en: {
      title: 'Arena',
      description:
        'Fair multi-model duels with frozen tools/constraints; live OpenCode traces and page preview.',
      path: '/arena',
    },
  },
  tasks: {
    zh: {
      title: '任务管理',
      description: '在前端创建与编辑评测任务：题面、脚手架、pytest；写入 tasks/ 后即可对战。',
      path: '/tasks',
    },
    en: {
      title: 'Tasks',
      description:
        'Create and edit evaluation tasks — brief, scaffold, pytest — then run them in the Arena.',
      path: '/tasks',
    },
  },
  leaderboard: {
    zh: {
      title: '排行榜',
      description: '按评测赛道查看模型通过率与综合表现（同赛道内分数可横比）。',
      path: '/leaderboard',
    },
    en: {
      title: 'Leaderboard',
      description: 'Model rankings by evaluation track — pass rates and aggregate scores.',
      path: '/leaderboard',
    },
  },
  outputs: {
    zh: {
      title: 'Agent 产出',
      description: '并排浏览各模型独立工作区中的代码与 HTML 预览。',
      path: '/outputs',
    },
    en: {
      title: 'Outputs',
      description: 'Side-by-side agent workspaces — code files and HTML previews.',
      path: '/outputs',
    },
  },
  comparison: {
    zh: {
      title: '对比',
      description: '多模型维度对比，辅助选择更适合任务的模型。',
      path: '/comparison',
    },
    en: {
      title: 'Comparison',
      description: 'Head-to-head multi-model comparison across key metrics.',
      path: '/comparison',
    },
  },
  models: {
    zh: {
      title: '模型配置',
      description: '配置参赛模型、API Key 与 Base URL，同步环境变量。',
      path: '/models',
    },
    en: {
      title: 'Models',
      description: 'Configure contestant models, API keys, and base URLs.',
      path: '/models',
    },
  },
}

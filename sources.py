# 新聞來源清單。filter=True 表示該來源不是 AI 專屬，只保留標題/摘要含 AI 關鍵字的文章。
SOURCES = [
    # 英文科技媒體
    {"name": "TechCrunch", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"name": "VentureBeat", "url": "https://feeds.feedburner.com/venturebeat/SZYF", "filter": True},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed"},
    {"name": "Wired", "url": "https://www.wired.com/feed/tag/ai/latest/rss"},
    {"name": "Ars Technica", "url": "https://arstechnica.com/ai/feed/"},
    {"name": "The Decoder", "url": "https://the-decoder.com/feed/"},
    {"name": "MarkTechPost", "url": "https://www.marktechpost.com/feed/"},
    {"name": "Simon Willison", "url": "https://simonwillison.net/atom/everything/"},
    # AI 公司官方部落格（Anthropic / Meta / Mistral 無官方 RSS，用社群維護的 feed）
    {"name": "OpenAI", "url": "https://openai.com/news/rss.xml"},
    {"name": "Anthropic", "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml"},
    {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml"},
    {"name": "Google AI", "url": "https://blog.google/technology/ai/rss/"},
    {"name": "Google Research", "url": "https://research.google/blog/rss/"},
    {"name": "Meta AI", "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_meta_ai.xml"},
    {"name": "Mistral AI", "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_mistral.xml"},
    {"name": "NVIDIA", "url": "https://blogs.nvidia.com/feed/", "filter": True},
    {"name": "Hugging Face", "url": "https://huggingface.co/blog/feed.xml"},
    {"name": "AWS Machine Learning", "url": "https://aws.amazon.com/blogs/machine-learning/feed/"},
    # 工程師導向的電子報
    {"name": "Latent Space", "url": "https://www.latent.space/feed"},
    {"name": "Interconnects", "url": "https://www.interconnects.ai/feed"},
    {"name": "Ahead of AI", "url": "https://magazine.sebastianraschka.com/feed"},
    # 社群 / 論文
    {"name": "r/LocalLLaMA", "url": "https://www.reddit.com/r/LocalLLaMA/top/.rss?t=day"},
    {"name": "Hacker News","url": "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+Claude+OR+OpenAI+OR+Gemini&points=100"},
    {"name": "HF Daily Papers", "url": "https://papers.takara.ai/api/feed"},
    {"name": "arXiv cs.AI", "url": "https://rss.arxiv.org/rss/cs.AI"},
    {"name": "arXiv cs.CL", "url": "https://rss.arxiv.org/rss/cs.CL"},
    # 中文媒體
    {"name": "iThome", "url": "https://www.ithome.com.tw/rss", "filter": True},
    {"name": "科技新報", "url": "https://technews.tw/category/ai/feed/"},
    {"name": "INSIDE", "url": "https://www.inside.com.tw/feed/rss", "filter": True},
    {"name": "量子位", "url": "https://www.qbitai.com/feed"},
]

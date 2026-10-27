"""每日 AI 日報：抓 RSS → 去重 → OpenAI 精選並寫繁中摘要 → 產生 docs/ 靜態網頁。"""
import calendar
import html
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI

from sources import SOURCES

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "docs"
TW = timezone(timedelta(hours=8))
LOOKBACK = timedelta(hours=24)
MAX_PER_SOURCE = 15
MODEL = "gpt-6-luna"

# 中文字也算 \w，所以 AI 不能用 \b 判斷邊界
AI_PATTERN = re.compile(
    r"(?<![A-Za-z])(AI|AGI|LLMs?|GPT|Claude|Gemini|Llama|OpenAI|Anthropic|DeepMind|Copilot|chatbots?)(?![A-Za-z])"
    r"|artificial intelligence|machine learning|neural|生成式|人工智慧|大模型|語言模型|機器學習|深度學習|機器人|聊天機器人",
    re.I,
)

SYSTEM_PROMPT = """你是資深 AI 產業編輯，負責每天早上為台灣讀者編一份 AI 日報。
從候選新聞中挑出最重要的 10–15 則，標準依序為：
1. 重大模型或產品發布（OpenAI、Anthropic、Google、Meta 等）
2. 影響產業走向的事件（大型融資、併購、政策法規、重要合作）
3. 有實質突破的研究成果
4. 開發者會關心的重要工具或開源專案
同一事件被多個來源報導時只選一則（優先官方來源或報導最完整的）。
略過行銷軟文、教學文、重複的小更新。arXiv 論文只有在確實重要時才選。

每則輸出：
- index：候選清單中的編號
- title：繁體中文標題（精簡、資訊量高，不要聳動）
- summary：2–3 句繁體中文摘要，講清楚發生什麼事與關鍵數字
- why：一句話說明為什麼值得關注
依重要性由高到低排序。全部使用台灣慣用的繁體中文用語。"""

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["index", "title", "summary", "why"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def clean(text, limit):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def fetch_source(src, since):
    try:
        req = urllib.request.Request(src["url"], headers={"User-Agent": "Mozilla/5.0 (daily-ai-report)"})
        feed = feedparser.parse(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        print(f"[skip] {src['name']}: {e}")
        return []

    items = []
    for e in feed.entries:
        t = e.get("published_parsed") or e.get("updated_parsed")
        if not t or not e.get("link"):
            continue
        published = datetime.fromtimestamp(calendar.timegm(t), timezone.utc)
        if published < since:
            continue
        title = clean(e.get("title"), 200)
        summary = clean(e.get("summary"), 300)
        if src.get("filter") and not AI_PATTERN.search(f"{title} {summary}"):
            continue
        items.append({"source": src["name"], "title": title, "summary": summary,
                      "link": e.link, "published": published.isoformat()})

    items.sort(key=lambda x: x["published"], reverse=True)
    print(f"[ok]   {src['name']}: {len(items[:MAX_PER_SOURCE])}")
    return items[:MAX_PER_SOURCE]


def collect():
    since = datetime.now(timezone.utc) - LOOKBACK
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = pool.map(lambda s: fetch_source(s, since), SOURCES)

    seen, items = set(), []
    for item in (i for r in results for i in r):
        keys = {item["link"].split("?")[0].rstrip("/"), re.sub(r"\W+", "", item["title"].lower())}
        if keys & seen:
            continue
        seen |= keys
        items.append(item)
    return items


def pick_top(candidates):
    listing = "\n".join(
        f"[{i}] ({c['source']}) {c['title']} — {c['summary']}" for i, c in enumerate(candidates)
    )
    client = OpenAI()
    resp = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=f"以下是過去 24 小時的 {len(candidates)} 則候選新聞：\n\n{listing}",
        text={"format": {"type": "json_schema", "name": "daily_report", "schema": SCHEMA, "strict": True}},
    )
    if resp.status != "completed":
        raise RuntimeError(f"OpenAI 未正常完成：status={resp.status}, {resp.incomplete_details}")

    picks = []
    for p in json.loads(resp.output_text)["items"]:
        if 0 <= p["index"] < len(candidates):
            c = candidates[p["index"]]
            picks.append({"title": p["title"], "summary": p["summary"], "why": p["why"],
                          "source": c["source"], "original_title": c["title"], "link": c["link"]})
    return picks


def build_site():
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    reports = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DATA_DIR.glob("*.json"), reverse=True)]
    SITE_DIR.mkdir(exist_ok=True)

    day_tpl = env.get_template("day.html")
    for i, r in enumerate(reports):
        newer = reports[i - 1]["date"] if i > 0 else None
        older = reports[i + 1]["date"] if i + 1 < len(reports) else None
        page = day_tpl.render(report=r, newer=newer, older=older)
        (SITE_DIR / f"{r['date']}.html").write_text(page, encoding="utf-8")
        if i == 0:
            (SITE_DIR / "index.html").write_text(page, encoding="utf-8")

    archive = env.get_template("archive.html").render(reports=reports)
    (SITE_DIR / "archive.html").write_text(archive, encoding="utf-8")


def main():
    now = datetime.now(TW)
    candidates = collect()
    print(f"候選新聞 {len(candidates)} 則")
    if not candidates:
        raise SystemExit("沒有抓到任何新聞，停止。")

    report = {"date": now.strftime("%Y-%m-%d"), "generated_at": now.isoformat(timespec="minutes"),
              "candidates": len(candidates), "items": pick_top(candidates)}
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / f"{report['date']}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    build_site()
    print(f"完成：{report['date']} 共 {len(report['items'])} 則")


if __name__ == "__main__":
    main()

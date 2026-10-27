"""每日 AI 日報：抓 RSS → 去重 → OpenAI 精選並寫繁中摘要 → 產生 docs/ 靜態網頁。"""
import calendar
import html
import json
import re
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

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

USER_AGENT = "Mozilla/5.0 (daily-ai-report)"
# 表情符號、網站 logo、頭像、追蹤像素等不適合當縮圖
BAD_IMAGE = re.compile(r"emoji|logo|gravatar|avatar|pixel|1x1|feedburner", re.I)

SYSTEM_PROMPT = """你是資深 AI 技術編輯，負責每天早上為台灣的 AI 工程師編一份技術日報。
讀者想掌握的是「AI 又有什麼新技術、又做出了什麼新東西」，不是商業新聞。
從候選新聞中挑出 12–20 則，並分成三級：
- headline（頭條）：剛好 1 則，今天最值得工程師知道的新技術或新產品
- important（重要）：6–9 則
- brief（快訊）：最多 10 則，值得知道但不需細讀的消息
挑選範圍為以下五類，不偏重特定國家或公司：
1. 模型：全世界閉源與開源模型的新發布、新能力（附規格、基準測試、價格等關鍵數字）
2. 研究：新方法、新架構、訓練技術、評測結果
3. 工程與基礎設施：開發框架、推論部署、Agent 開發、硬體、API 與平台變更
4. 應用：AI 實際做到了以前做不到的事
5. 安全：技術層面的漏洞、攻擊手法與防禦
硬體規格與效能屬於技術新聞；硬體的營收、供需、股價則屬商業新聞。
融資、IPO、併購、財報、人事、裁員、政策法規、訴訟、犯罪等商業與社會新聞：
不得列為 headline 或 important；只有影響重大者才放進 brief，且最多 3 則。
同一事件被多個來源報導時只選一則（優先官方或原始來源）。
略過行銷軟文、入門教學、重複的小更新。arXiv 論文要有明確的新方法或顯著結果才選。

每則輸出：
- index：候選清單中的編號
- tier：headline / important / brief
- title：繁體中文標題（精簡、資訊量高，不要聳動）
- summary：headline 與 important 寫 2–3 句繁體中文摘要，講清楚做了什麼、怎麼做、關鍵數字；brief 只寫一句
- why：一句話從工程師角度說明新在哪裡、能做到什麼以前做不到的事；brief 填空字串
依 headline、important、brief 的順序輸出，同級內依重要性由高到低。全部使用台灣慣用的繁體中文用語。"""

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "tier": {"type": "string", "enum": ["headline", "important", "brief"]},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["index", "tier", "title", "summary", "why"],
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


def http_get(url, timeout, limit=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(limit)


def entry_image(e):
    """從 RSS 項目找圖片：media 標籤 → enclosure → 內文 <img>。"""
    urls = [m.get("url") for m in e.get("media_content", []) + e.get("media_thumbnail", [])
            if "video" not in m.get("medium", "") + m.get("type", "")
            and "audio" not in m.get("medium", "") + m.get("type", "")]
    urls += [l.get("href") for l in e.get("links", [])
             if l.get("rel") == "enclosure" and l.get("type", "").startswith("image")]
    body = " ".join([e.get("summary", "")] + [c.get("value", "") for c in e.get("content", [])])
    urls += [html.unescape(u) for u in re.findall(r"<img[^>]+src=[\"']([^\"']+)", body)]
    return next((u for u in urls if u and not BAD_IMAGE.search(u)), "")


def page_image(url):
    """抓原文網頁的 og:image / twitter:image。"""
    try:
        page = http_get(url, timeout=10, limit=300_000).decode("utf-8", "ignore")
    except Exception:
        return ""
    m = re.search(r"<meta[^>]+(?:property|name)=[\"'](?:og:image|twitter:image)[\"'][^>]*>", page, re.I)
    src = m and re.search(r"content=[\"']([^\"']+)", m.group(0))
    img = urljoin(url, html.unescape(src.group(1))) if src else ""
    return "" if BAD_IMAGE.search(img) else img


def fetch_source(src, since):
    try:
        feed = feedparser.parse(http_get(src["url"], timeout=30))
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
        items.append({"source": src["name"], "title": title, "summary": summary, "link": e.link,
                      "image": entry_image(e), "published": published.isoformat()})

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
            picks.append({"tier": p["tier"], "title": p["title"], "summary": p["summary"], "why": p["why"],
                          "source": c["source"], "original_title": c["title"], "link": c["link"],
                          "image": c["image"]})

    # 確保剛好一則頭條，並依級別排序
    headlines = [p for p in picks if p["tier"] == "headline"]
    for p in headlines[1:]:
        p["tier"] = "important"
    if not headlines and picks:
        picks[0]["tier"] = "headline"
    order = {"headline": 0, "important": 1, "brief": 2}
    picks.sort(key=lambda p: order[p["tier"]])

    # RSS 沒附圖的頭條與重要新聞，改抓原文網頁的封面圖
    missing = [p for p in picks if not p["image"] and p["tier"] != "brief"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for p, img in zip(missing, pool.map(lambda p: page_image(p["link"]), missing)):
            p["image"] = img
    return picks


def build_site():
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    env.filters["hue"] = lambda s: zlib.crc32(s.encode()) % 360
    env.filters["weekday"] = lambda d: "一二三四五六日"[date.fromisoformat(d).weekday()]
    reports = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DATA_DIR.glob("*.json"), reverse=True)]
    for r in reports:  # 改版前的日報沒有分級：第一則當頭條，其餘當重要
        for i, item in enumerate(r["items"]):
            item.setdefault("tier", "headline" if i == 0 else "important")
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

# AI 日報

每天早上自動從約 31 個來源（英文科技媒體、AI 公司官方部落格、工程師電子報、Reddit / Hacker News / 論文、中文媒體）抓取過去 24 小時的新聞，由 OpenAI 模型以 AI 工程師的角度挑出新技術、新產品與研究重點（財經商業新聞只列快訊）並寫成繁中摘要，發布到 GitHub Pages。

## 流程

```
GitHub Actions（每天 UTC 22:30 = 台灣 06:30）
 → main.py 抓 RSS（sources.py）→ 去重
 → OpenAI（gpt-6-luna）精選並寫繁中標題、摘要、為何重要
 → data/YYYY-MM-DD.json
 → docs/index.html（最新）、docs/YYYY-MM-DD.html、docs/archive.html
 → commit 回 repo → GitHub Pages 發布
```

## 部署步驟

1. 在 GitHub 建立新 repo（例如 `daily-ai-report`），把這個資料夾推上去：
   ```bash
   git init -b main
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/<你的帳號>/daily-ai-report.git
   git push -u origin main
   ```
2. repo → **Settings → Secrets and variables → Actions → New repository secret**
   名稱 `OPENAI_API_KEY`，值填你的 OpenAI API key（[platform.openai.com](https://platform.openai.com/api-keys) 取得）。
3. repo → **Settings → Pages** → Source 選 **Deploy from a branch**，Branch 選 `main`、資料夾選 `/docs`。
4. repo → **Actions → Daily AI Report → Run workflow** 手動跑第一次。
5. 完成後網站在 `https://<你的帳號>.github.io/daily-ai-report/`。

之後每天會自動更新。

## 本機執行

```bash
pip install -r requirements.txt
set OPENAI_API_KEY=sk-...   # PowerShell: $env:OPENAI_API_KEY="sk-..."
python main.py
```

產出的網頁在 `docs/index.html`，直接用瀏覽器開即可。

## 調整

- **新增 / 移除來源**：編輯 `sources.py`。非 AI 專屬的來源加 `"filter": True`，只保留含 AI 關鍵字的文章。
- **挑選標準、則數**：改 `main.py` 的 `SYSTEM_PROMPT`。
- **換模型**：改 `main.py` 的 `MODEL`（例如 `gpt-6.1-terra` 品質較好、成本約 10 倍）。
- **更新時間**：改 `.github/workflows/daily.yml` 的 cron（UTC 時間）。

## 注意

- 每天一次 API 呼叫，以 gpt-6-luna 計約 0.01 美元以下（依候選新聞量浮動）。
- 單一來源失敗會被略過，不影響整份日報；Actions 的 log 會列出每個來源抓到幾則。
- Anthropic / Meta / Mistral 沒有官方 RSS，使用社群維護的 feed（[Olshansk/rss-feeds](https://github.com/Olshansk/rss-feeds)），可能偶爾延遲。
- GitHub 排程可能延遲 10–60 分鐘。

"""過去の号一覧ページを生成する"""
import os
from pathlib import Path
from datetime import datetime

docs_dir = Path("docs")
archive_dir = docs_dir / "archive"
archive_dir.mkdir(parents=True, exist_ok=True)

# アーカイブのHTMLファイルを日付順で収集
archives = sorted(
    [f for f in archive_dir.glob("brew_daily_*.html")],
    reverse=True
)

rows = ""
for f in archives:
    date_str = f.stem.replace("brew_daily_", "")
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        label = dt.strftime("%Y年%m月%d日")
    except Exception:
        label = date_str
    rows += f'<li><a href="archive/{f.name}">📰 {label} 号</a></li>\n'

if not rows:
    rows = '<li>まだアーカイブがありません</li>'

html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🍺 BREW DAILY バックナンバー</title>
<style>
  body {{ font-family: 'Meiryo', sans-serif; background: #FFF8E7;
         max-width: 700px; margin: 2rem auto; padding: 1rem; }}
  h1 {{ color: #3D2B1F; border-bottom: 3px solid #F5A623; padding-bottom: .5rem; }}
  a {{ color: #1E6B9E; text-decoration: none; font-size: 1.1rem; }}
  a:hover {{ text-decoration: underline; }}
  li {{ margin: .8rem 0; }}
  .back {{ margin-top: 2rem; }}
</style>
</head>
<body>
  <h1>🍺 BREW DAILY バックナンバー</h1>
  <ul>{rows}</ul>
  <p class="back"><a href="index.html">← 最新号に戻る</a></p>
</body>
</html>"""

(docs_dir / "archive.html").write_text(html, encoding="utf-8")
print(f"✅ アーカイブ一覧を生成しました ({len(archives)}件)")

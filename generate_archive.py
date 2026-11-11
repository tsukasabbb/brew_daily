"""バックナンバー一覧ページ（月別 + 記事検索）を生成する

- docs/archive/brew_daily_YYYYMMDD.html を全て読み込み、記事を抽出して検索用データを作る
- docs/archive.html に「月別のバックナンバー一覧」と「キーワード・カテゴリ検索」を出力する
- 旧形式（2026年10月18日号まで）の記事には id="article-N" を付け、検索結果から該当記事へ直接飛べるようにする
"""
import html as htmlmod
import json
import re
from datetime import datetime
from pathlib import Path

docs_dir = Path("docs")
archive_dir = docs_dir / "archive"
archive_dir.mkdir(parents=True, exist_ok=True)

# 一覧・検索に載せない号（ファイルは削除しない）
# 20260602: 開発時のデモ実行で生成された号（架空の内容を含む）
EXCLUDE = {"20260602"}

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
CATEGORIES = ["麦芽", "ホップ", "水", "副原料"]


def text(fragment: str) -> str:
    """HTML断片をプレーンテキストにする"""
    if not fragment:
        return ""
    s = re.sub(r"<br\s*/?>|</p>", "\n", fragment)
    s = re.sub(r"<[^>]+>", "", s)
    s = htmlmod.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s)
    return s.strip()


def first(pattern: str, s: str) -> str:
    m = re.search(pattern, s, re.S)
    return m.group(1) if m else ""


def all_spans(pattern: str, s: str) -> list:
    return [text(x) for x in re.findall(pattern, s, re.S)]


def add_article_ids(path: Path, src: str) -> str:
    """id の無い旧形式の <article> に id="article-N" を付ける（何度実行しても同じ結果）"""
    counter = {"n": 0}

    def repl(m):
        counter["n"] += 1
        tag = m.group(0)
        if " id=" in tag:
            return tag
        return tag.replace("<article", f'<article id="article-{counter["n"]}"', 1)

    new = re.sub(r"<article\b[^>]*>", repl, src)
    if new != src:
        path.write_text(new, encoding="utf-8")
    return new


def parse_category(raw: str) -> str:
    for c in CATEGORIES:
        if c in raw and not (c == "水" and "副原料" in raw):
            return c
    return raw.strip()


def parse_issue(path: Path, date_str: str) -> list:
    src = path.read_text(encoding="utf-8")
    src = add_article_ids(path, src)
    articles = []
    for i, m in enumerate(re.finditer(r"<article\b([^>]*)>(.*?)</article>", src, re.S), 1):
        attrs, body = m.group(1), m.group(2)
        anchor = first(r'id="([^"]+)"', attrs) or f"article-{i}"

        if 'class="article-card"' in attrs:  # 旧形式（〜10/18）
            category = parse_category(text(first(r'<span class="category"[^>]*>(.*?)</span>', body)))
            headline = text(first(r'<h2 class="article-title">(.*?)</h2>', body))
            deck = text(first(r'<div class="highlight">(.*?)</div>', body)).lstrip("💡 ").strip()
            source = text(first(r'<span class="brewery">(.*?)</span>', body)).lstrip("🏭 ").strip()
            country = text(first(r'<span class="country">(.*?)</span>', body)).lstrip("🌍 ").strip()
            pubdate = ""
            content = text(first(r'<div class="summary-body">(.*?)</div>\s*<div class="analysis-box">', body))
            analysis = text(first(r'<p class="analysis-text">(.*?)</p>', body))
            stars = text(first(r'<span class="popularity">(.*?)</span>', body))
        else:  # 新形式（10/19〜）
            category = first(r'data-category="([^"]+)"', attrs) or parse_category(
                text(first(r'<span class="article-category">(.*?)</span>', body)))
            headline = text(first(r'<h2 class="article-headline">(.*?)</h2>', body))
            deck = text(first(r'<p class="article-deck">(.*?)</p>', body))
            byline = all_spans(r"<span>(.*?)</span>", first(r'<div class="article-byline">(.*?)</div>', body))
            pubdate = next((b.replace("発表日:", "").strip() for b in byline if b.startswith("発表日")), "")
            byline = [b for b in byline if not b.startswith("発表日")]
            source = byline[0] if byline else ""
            country = byline[1] if len(byline) > 1 else ""
            content = text(first(r'<div class="article-body">(.*?)</div>', body))
            analysis = text(first(r'<div class="analysis">.*?<p>(.*?)</p>', body))
            stars = text(first(r'<span class="article-popularity">(.*?)</span>', body))

        url = htmlmod.unescape(first(r'<a href="(https?://[^"]+)"[^>]*>\s*(?:📰\s*)?オリジナル記事', body))
        if not headline:
            continue
        articles.append({
            "d": date_str, "f": path.name, "a": anchor, "r": i,
            "c": category, "s": stars.count("⭐"),
            "h": headline, "k": deck, "src": source, "co": country, "pd": pubdate,
            "b": content, "an": analysis, "u": url,
        })
    return articles


archives = sorted(archive_dir.glob("brew_daily_*.html"), reverse=True)

issues = []      # 号ごとの情報（月別一覧用）
index = []       # 記事ごとの情報（検索用）
for f in archives:
    date_str = f.stem.replace("brew_daily_", "")
    if date_str in EXCLUDE:
        continue
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        continue
    arts = parse_issue(f, date_str)
    index.extend(arts)
    issues.append({"dt": dt, "file": f.name, "articles": arts})

# ── 月別一覧の HTML ──
months = {}
for it in issues:
    months.setdefault((it["dt"].year, it["dt"].month), []).append(it)

esc = htmlmod.escape
month_html = ""
for n, ((y, mth), its) in enumerate(months.items()):
    n_articles = sum(len(i["articles"]) for i in its)
    rows = ""
    for it in its:
        dt = it["dt"]
        label = f"{dt.month}月{dt.day}日（{WEEKDAYS[dt.weekday()]}）号"
        heads = "".join(
            f'<li><a href="archive/{it["file"]}#{esc(a["a"])}">'
            f'<span class="cat cat-{esc(a["c"])}">{esc(a["c"])}</span>{esc(a["h"])}</a></li>'
            for a in it["articles"]
        )
        rows += (
            f'<li class="issue"><details><summary>'
            f'<span class="label">{label}</span>'
            f'<span class="count">{len(it["articles"])}本</span></summary>'
            f'<ol class="heads">{heads}</ol>'
            f'<a class="open-issue" href="archive/{it["file"]}">この号を開く →</a>'
            f'</details></li>\n'
        )
    open_attr = " open" if n == 0 else ""
    month_html += (
        f'<details class="month"{open_attr}><summary class="month-head">'
        f'<span class="month-name">{y}年{mth}月</span>'
        f'<span class="month-meta">{len(its)}号・{n_articles}記事</span></summary>'
        f'<ul class="issues">{rows}</ul></details>\n'
    )
if not month_html:
    month_html = '<p class="empty">まだアーカイブがありません</p>'

# 検索用データは別ファイルにして、一覧ページ本体を軽く保つ
(archive_dir / "search-index.json").write_text(
    json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
month_options = "".join(f'<option value="{y}{m:02d}">{y}年{m}月</option>' for (y, m) in months)
version = issues[0]["file"][11:19] if issues else "0"
latest_label = ""
if issues:
    d = issues[0]["dt"]
    oldest = issues[-1]["dt"]
    latest_label = f"{oldest.year}年{oldest.month}月{oldest.day}日〜{d.year}年{d.month}月{d.day}日・全{len(issues)}号・{len(index)}記事"

html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BREW DAILY — バックナンバー</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --amber:#C8860A; --amber2:#F5A623;
    --ink:#0F0C08; --ink2:#3D2B1F; --muted:#7A6A5A;
    --paper:#F9F6F0; --card:#fff; --rule:#D4C4A8; --blue:#1A4E8C;
    --mark:#FCE7B2;
    --c-malt:#8B6914; --c-hop:#4A7C2F; --c-water:#1A6B8C; --c-adj:#9B4E9E;
  }}
  *,*::before,*::after{{margin:0;padding:0;box-sizing:border-box;}}
  html{{font-size:16px;}}
  body{{
    font-family:'Noto Sans JP',sans-serif;
    background:var(--paper); color:var(--ink);
    min-height:100vh; -webkit-font-smoothing:antialiased;
  }}
  header{{
    background:var(--ink); color:#fff;
    padding:2rem 1.5rem 1.5rem; text-align:center;
    position:relative; overflow:hidden;
  }}
  header::before{{
    content:'';position:absolute;inset:0;
    background:repeating-linear-gradient(90deg,rgba(200,134,10,.07) 0,rgba(200,134,10,.07) 1px,transparent 1px,transparent 60px);
    pointer-events:none;
  }}
  .eyebrow{{font-size:.6rem;letter-spacing:.35em;color:var(--amber2);text-transform:uppercase;margin-bottom:.7rem;}}
  h1{{font-family:'Playfair Display',serif;font-size:clamp(2rem,6vw,3.5rem);font-weight:900;color:#fff;letter-spacing:.06em;line-height:1;}}
  .rule{{border:none;height:1px;background:linear-gradient(90deg,transparent,var(--amber),transparent);margin:.8rem auto;width:min(360px,70%);}}
  .subtitle{{font-size:.7rem;color:rgba(255,255,255,.45);letter-spacing:.08em;}}

  main{{max-width:760px;margin:0 auto;padding:2rem 1.5rem 4rem;}}
  .section-label{{
    font-size:.62rem;font-weight:700;letter-spacing:.28em;text-transform:uppercase;color:var(--amber);
    border-bottom:1px solid var(--rule);padding-bottom:.5rem;margin-bottom:1rem;
    display:flex;align-items:center;gap:.5rem;
  }}
  .section-label::before{{content:'';display:block;width:14px;height:2px;background:var(--amber);}}

  /* ── 検索 ── */
  .search{{background:var(--card);border:1px solid var(--rule);border-radius:6px;padding:1rem;margin-bottom:2rem;
    position:sticky;top:0;z-index:5;box-shadow:0 2px 10px rgba(15,12,8,.05);}}
  .search-row{{display:flex;gap:.5rem;}}
  .search input[type=search]{{
    flex:1;min-width:0;font:inherit;font-size:1rem;padding:.65rem .8rem;
    border:1px solid var(--rule);border-radius:4px;background:var(--paper);color:var(--ink);
  }}
  .search input[type=search]:focus{{outline:2px solid var(--amber);outline-offset:1px;background:#fff;}}
  .filters{{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.7rem;align-items:center;}}
  .chip{{
    font:inherit;font-size:.75rem;padding:.3rem .75rem;border-radius:999px;cursor:pointer;
    border:1px solid var(--rule);background:#fff;color:var(--ink2);
  }}
  .chip[aria-pressed=true]{{background:var(--ink);color:#fff;border-color:var(--ink);}}
  .filters select{{font:inherit;font-size:.75rem;padding:.3rem .5rem;border:1px solid var(--rule);border-radius:4px;background:#fff;color:var(--ink2);margin-left:auto;}}
  .hint{{font-size:.7rem;color:var(--muted);margin-top:.6rem;}}
  .status{{font-size:.8rem;color:var(--ink2);margin-bottom:1rem;}}
  .status strong{{color:var(--amber);font-size:1rem;}}

  .results{{list-style:none;}}
  .result{{background:var(--card);border:1px solid var(--rule);border-left:4px solid var(--cc,var(--amber));border-radius:4px;padding:.9rem 1rem;margin-bottom:.8rem;}}
  .result-meta{{display:flex;flex-wrap:wrap;gap:.3rem .7rem;font-size:.7rem;color:var(--muted);margin-bottom:.35rem;align-items:center;}}
  .result h3{{font-size:.95rem;line-height:1.5;margin-bottom:.35rem;}}
  .result h3 a{{color:var(--ink);text-decoration:none;}}
  .result h3 a:hover{{color:var(--blue);text-decoration:underline;}}
  .snippet{{font-size:.8rem;line-height:1.75;color:var(--ink2);}}
  .result-links{{margin-top:.5rem;font-size:.72rem;display:flex;gap:1rem;flex-wrap:wrap;}}
  .result-links a{{color:var(--blue);}}
  mark{{background:var(--mark);color:inherit;padding:0 .1em;border-radius:2px;}}
  .more{{display:block;margin:1rem auto;font:inherit;font-size:.8rem;padding:.5rem 1.2rem;border:1px solid var(--rule);background:#fff;border-radius:4px;cursor:pointer;}}
  .noresult{{padding:1.5rem;text-align:center;color:var(--muted);font-size:.85rem;background:var(--card);border:1px dashed var(--rule);border-radius:4px;}}

  .cat{{display:inline-block;font-size:.62rem;font-weight:700;color:#fff;padding:.1rem .45rem;border-radius:3px;margin-right:.5rem;vertical-align:.1em;background:var(--muted);flex-shrink:0;}}
  .cat-麦芽{{background:var(--c-malt);}} .cat-ホップ{{background:var(--c-hop);}}
  .cat-水{{background:var(--c-water);}} .cat-副原料{{background:var(--c-adj);}}

  /* ── 月別一覧 ── */
  .summary-line{{font-size:.75rem;color:var(--muted);margin-bottom:1rem;}}
  details.month{{background:var(--card);border:1px solid var(--rule);border-radius:6px;margin-bottom:1rem;overflow:hidden;}}
  .month-head{{list-style:none;cursor:pointer;display:flex;align-items:baseline;gap:.8rem;padding:1rem 1.1rem;background:var(--ink);color:#fff;}}
  .month-head::-webkit-details-marker{{display:none;}}
  .month-head::before{{content:'▸';color:var(--amber2);transition:transform .15s;display:inline-block;}}
  details.month[open] > .month-head::before{{transform:rotate(90deg);}}
  .month-name{{font-family:'Playfair Display','Noto Sans JP',serif;font-size:1.2rem;font-weight:700;}}
  .month-meta{{font-size:.7rem;color:rgba(255,255,255,.55);margin-left:auto;}}
  ul.issues{{list-style:none;}}
  li.issue + li.issue{{border-top:1px solid var(--rule);}}
  li.issue summary{{list-style:none;cursor:pointer;display:flex;align-items:center;gap:.8rem;padding:.8rem 1.1rem;font-size:.88rem;font-weight:500;color:var(--ink2);}}
  li.issue summary::-webkit-details-marker{{display:none;}}
  li.issue summary::before{{content:'📰';}}
  li.issue summary:hover{{background:var(--paper);}}
  li.issue .label{{flex:1;}}
  li.issue .count{{font-size:.7rem;color:var(--muted);}}
  li.issue summary::after{{content:'＋';color:var(--amber);font-weight:700;}}
  li.issue details[open] summary::after{{content:'－';}}
  ol.heads{{list-style:none;padding:0 1.1rem .4rem 2.9rem;}}
  ol.heads li{{padding:.35rem 0;font-size:.8rem;line-height:1.55;display:flex;align-items:baseline;}}
  ol.heads a{{color:var(--ink2);text-decoration:none;}}
  ol.heads a:hover{{color:var(--blue);text-decoration:underline;}}
  .open-issue{{display:inline-block;margin:0 1.1rem .9rem 2.9rem;font-size:.75rem;color:var(--blue);}}
  .empty{{color:var(--muted);font-size:.85rem;}}

  .back{{margin-top:2rem;font-size:.8rem;}}
  .back a{{color:var(--blue);text-decoration:none;border-bottom:1px solid currentColor;padding-bottom:1px;}}
  .back a:hover{{color:var(--amber);}}
  footer{{background:var(--ink);color:rgba(255,255,255,.3);text-align:center;padding:1.5rem;font-size:.68rem;line-height:1.8;}}
  footer strong{{color:var(--amber2);}}
  [hidden]{{display:none !important;}}
  @media(max-width:480px){{
    main{{padding:1.25rem 1rem 3rem;}}
    .search{{position:static;}}
    .filters select{{margin-left:0;}}
    ol.heads{{padding-left:1.1rem;}}
    .open-issue{{margin-left:1.1rem;}}
  }}
</style>
</head>
<body>
<header>
  <p class="eyebrow">世界のブルワリー最新情報マガジン</p>
  <h1>BREW DAILY</h1>
  <div class="rule"></div>
  <p class="subtitle">バックナンバー</p>
</header>
<main>
  <section class="search" role="search">
    <div class="search-row">
      <input type="search" id="q" placeholder="キーワードで記事を検索（例：ホップ 収穫、GABF、キリン）" autocomplete="off" aria-label="記事を検索">
    </div>
    <div class="filters" id="filters">
      <button class="chip" type="button" data-cat="" aria-pressed="true">すべて</button>
      <button class="chip" type="button" data-cat="麦芽" aria-pressed="false">🌾 麦芽</button>
      <button class="chip" type="button" data-cat="ホップ" aria-pressed="false">🌿 ホップ</button>
      <button class="chip" type="button" data-cat="水" aria-pressed="false">💧 水</button>
      <button class="chip" type="button" data-cat="副原料" aria-pressed="false">🌽 副原料</button>
      <select id="month" aria-label="月で絞り込み"><option value="">すべての月</option>{month_options}</select>
    </div>
    <p class="hint">見出し・本文・編集部の考察・醸造所名・国名から検索します。スペース区切りで複数語のAND検索ができます。</p>
  </section>

  <section id="search-results" hidden>
    <p class="section-label">Search</p>
    <p class="status" id="status"></p>
    <ol class="results" id="results"></ol>
    <button class="more" id="more" type="button" hidden>さらに表示</button>
  </section>

  <section id="archive-list">
    <p class="section-label">Archive — 月別</p>
    <p class="summary-line">{latest_label}</p>
    {month_html}
  </section>

  <p class="back"><a href="index.html">← 最新号に戻る</a></p>
</main>
<footer>
  <p><strong>BREW DAILY</strong> — 世界の醸造所公式情報を AI が毎朝収集・翻訳・解説</p>
</footer>
<script>
(function () {{
  var DATA = null;
  var WD = ['日','月','火','水','木','金','土'];
  var PAGE = 30;
  var $q = document.getElementById('q'), $month = document.getElementById('month');
  var $res = document.getElementById('results'), $status = document.getElementById('status');
  var $sec = document.getElementById('search-results'), $list = document.getElementById('archive-list');
  var $more = document.getElementById('more');
  var state = {{ cat: '', shown: PAGE }};

  // 全角/半角・大文字/小文字の違いを吸収
  function norm(s) {{ return (s || '').normalize('NFKC').toLowerCase(); }}

  function esc(s) {{
    return (s || '').replace(/[&<>"']/g, function (c) {{
      return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c];
    }});
  }}
  function reEsc(s) {{ return s.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&'); }}
  function highlight(s, terms) {{
    var out = esc(s);
    if (!terms.length) return out;
    var re = new RegExp('(' + terms.map(function (t) {{ return reEsc(esc(t)); }}).join('|') + ')', 'gi');
    return out.replace(re, '<mark>$1</mark>');
  }}
  function snippet(a, terms) {{
    var src = (a.b + '\\n' + a.an).replace(/\\n/g, ' ');
    if (!terms.length) return src.slice(0, 120) + (src.length > 120 ? '…' : '');
    var n = norm(src), pos = -1;
    for (var i = 0; i < terms.length && pos < 0; i++) pos = n.indexOf(terms[i]);
    if (pos < 0) return a.k || src.slice(0, 120) + '…';
    var start = Math.max(0, pos - 50), end = Math.min(src.length, pos + 90);
    return (start > 0 ? '…' : '') + src.slice(start, end) + (end < src.length ? '…' : '');
  }}
  function dateLabel(d) {{
    var dt = new Date(+d.slice(0, 4), +d.slice(4, 6) - 1, +d.slice(6, 8));
    return dt.getFullYear() + '年' + (dt.getMonth() + 1) + '月' + dt.getDate() + '日（' + WD[dt.getDay()] + '）号';
  }}
  var COLORS = {{'麦芽':'var(--c-malt)','ホップ':'var(--c-hop)','水':'var(--c-water)','副原料':'var(--c-adj)'}};

  function run(keepShown) {{
    var raw = $q.value.trim();
    var terms = norm(raw).split(/\\s+/).filter(Boolean);
    var month = $month.value, cat = state.cat;
    var active = terms.length || month || cat;
    $sec.hidden = !active; $list.hidden = !!active;
    if (!keepShown) state.shown = PAGE;
    syncUrl(raw, cat, month);
    if (!active) return;
    if (!DATA) {{ $status.textContent = '検索データを読み込み中…'; $res.innerHTML = ''; $more.hidden = true; return; }}

    var hits = DATA.filter(function (a) {{
      if (cat && a.c !== cat) return false;
      if (month && a.d.slice(0, 6) !== month) return false;
      for (var i = 0; i < terms.length; i++) if (a._t.indexOf(terms[i]) < 0) return false;
      return true;
    }});
    // 見出しに含まれる記事を優先し、その中では新しい号順
    hits.sort(function (x, y) {{
      var hx = terms.every(function (t) {{ return norm(x.h).indexOf(t) >= 0; }}) ? 1 : 0;
      var hy = terms.every(function (t) {{ return norm(y.h).indexOf(t) >= 0; }}) ? 1 : 0;
      return (hy - hx) || (y.d.localeCompare(x.d)) || (x.r - y.r);
    }});
    var issuesHit = {{}};
    hits.forEach(function (a) {{ issuesHit[a.d] = 1; }});
    $status.innerHTML = hits.length
      ? '<strong>' + hits.length + '</strong> 件の記事（' + Object.keys(issuesHit).length + '号）が見つかりました'
      : '';
    if (!hits.length) {{
      $res.innerHTML = '<li class="noresult">該当する記事が見つかりませんでした。<br>別のキーワードや、カテゴリ・月の絞り込みを外してお試しください。</li>';
      $more.hidden = true;
      return;
    }}
    var termsRaw = raw.split(/\\s+/).filter(Boolean);
    var hlTerms = termsRaw.concat(termsRaw.map(function (t) {{ return t.normalize('NFKC'); }}));
    $res.innerHTML = hits.slice(0, state.shown).map(function (a) {{
      var link = 'archive/' + a.f + '#' + a.a;
      var meta = [
        '<span class="cat cat-' + esc(a.c) + '">' + esc(a.c) + '</span>',
        '<span>' + dateLabel(a.d) + '</span>',
        a.src ? '<span>' + highlight(a.src, hlTerms) + '</span>' : '',
        a.co ? '<span>' + highlight(a.co, hlTerms) + '</span>' : ''
      ].join('');
      return '<li class="result" style="--cc:' + (COLORS[a.c] || 'var(--amber)') + '">' +
        '<div class="result-meta">' + meta + '</div>' +
        '<h3><a href="' + link + '">' + highlight(a.h, hlTerms) + '</a></h3>' +
        '<p class="snippet">' + highlight(snippet(a, terms), hlTerms) + '</p>' +
        '<p class="result-links"><a href="' + link + '">この号で読む →</a>' +
        (a.u ? '<a href="' + esc(a.u) + '" target="_blank" rel="noopener">オリジナル記事 ↗</a>' : '') +
        '</p></li>';
    }}).join('');
    $more.hidden = hits.length <= state.shown;
    $more.textContent = 'さらに表示（残り ' + (hits.length - state.shown) + ' 件）';
  }}

  function syncUrl(q, cat, month) {{
    try {{
      var p = new URLSearchParams();
      if (q) p.set('q', q);
      if (cat) p.set('cat', cat);
      if (month) p.set('m', month);
      var s = p.toString();
      history.replaceState(null, '', location.pathname + (s ? '?' + s : ''));
    }} catch (e) {{}}
  }}
  function setCat(cat) {{
    state.cat = cat;
    document.querySelectorAll('#filters .chip').forEach(function (b) {{
      b.setAttribute('aria-pressed', String(b.dataset.cat === cat));
    }});
  }}

  var timer;
  $q.addEventListener('input', function () {{ clearTimeout(timer); timer = setTimeout(function () {{ run(); }}, 120); }});
  $month.addEventListener('change', function () {{ run(); }});
  document.getElementById('filters').addEventListener('click', function (e) {{
    var b = e.target.closest('.chip'); if (!b) return;
    setCat(b.dataset.cat); run();
  }});
  $more.addEventListener('click', function () {{ state.shown += PAGE; run(true); }});
  document.addEventListener('keydown', function (e) {{
    if (e.key === '/' && document.activeElement !== $q) {{ e.preventDefault(); $q.focus(); }}
    if (e.key === 'Escape' && document.activeElement === $q) {{ $q.value = ''; run(); }}
  }});

  // URL の ?q=…&cat=…&m=… から検索状態を復元（検索結果を共有できる）
  var p = new URLSearchParams(location.search);
  $q.value = p.get('q') || '';
  if (p.get('cat')) setCat(p.get('cat'));
  if (p.get('m')) $month.value = p.get('m');
  run();

  fetch('archive/search-index.json?v={version}')
    .then(function (r) {{ if (!r.ok) throw new Error(r.status); return r.json(); }})
    .then(function (d) {{
      d.forEach(function (a) {{ a._t = norm([a.h, a.k, a.src, a.co, a.b, a.an].join('\\n')); }});
      DATA = d; run(true);
    }})
    .catch(function () {{
      DATA = [];
      $status.textContent = '検索データを読み込めませんでした。ページを再読み込みしてください。';
    }});
}})();
</script>
</body>
</html>"""

(docs_dir / "archive.html").write_text(html, encoding="utf-8")
print(f"✅ アーカイブ一覧を生成しました ({len(issues)}号・{len(index)}記事・{len(months)}か月)")

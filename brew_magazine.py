"""
BREW DAILY - 世界のブルワリー最新情報マガジン
毎朝7時に実行: 世界中の醸造所公式情報を収集し、日本語マガジンを生成する
"""

import anthropic
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# --- 設定 ---
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

MODEL = "claude-opus-4-8"

# 検索対象の醸造所・業界団体（オフィシャルソース）
BREWERY_SOURCES = [
    # 大手ブルワリー
    "Sierra Nevada Brewing",
    "Dogfish Head Craft Brewery",
    "New Belgium Brewing",
    "Boston Beer Company Samuel Adams",
    "Anheuser-Busch InBev",
    "Heineken",
    "Carlsberg Group",
    "Asahi Breweries",
    "Kirin Brewery",
    "Sapporo Breweries",
    "Yebisu Beer",
    "Brasserie Dupont Belgium",
    "Weihenstephan Germany",
    "Paulaner Munich",
    "BrewDog Scotland",
    "Guinness Diageo",
    # 業界団体・研究機関
    "Brewers Association",
    "Institute of Brewing and Distilling",
    "American Homebrewers Association",
    "European Brewery Convention",
    "Malt Barley Research",
    "Hop Research Center",
]

# 検索キーワード（麦芽・ホップ・水・副原料）
SEARCH_TOPICS = [
    "new malt variety brewing 2025",
    "hop harvest aroma brewing official",
    "water chemistry brewing techniques brewery",
    "adjunct ingredients craft beer innovation",
    "barley malt quality brewery announcement",
    "hops new release brewery",
    "brewing water minerals official report",
    "rice corn adjunct brewing",
    "specialty malt release brewery",
    "experimental hop variety official",
]


def search_brewery_news(client: anthropic.Anthropic) -> list[dict]:
    """Claude の web_search ツールを使って醸造所の最新ニュースを収集する"""
    print("🔍 醸造所ニュースを検索中...")

    search_queries = [
        "site:sierranevada.com OR site:dogfish.com OR site:newbelgium.com malt hops water brewing 2025",
        "site:brewersassociation.org malt hops adjunct ingredients 2025",
        "site:asahibeer.co.jp OR site:kirin.co.jp OR site:sapporobeer.jp 麦芽 ホップ 副原料 2025",
        "brewery official announcement malt hop water ingredient innovation 2025",
        "craft brewery new beer malt variety hops water brewing technique site:.com 2025",
        "Weihenstephan Paulaner Heineken Carlsberg brewing ingredients news 2025",
        "BrewDog Guinness Anheuser-Busch malt hops water adjunct official 2025",
        "brewing industry malt barley hops shortage supply official report 2025",
    ]

    all_articles = []

    for query in search_queries[:5]:  # API節約のため最初の5クエリ
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                tools=[
                    {"type": "web_search_20260209", "name": "web_search"},
                ],
                messages=[
                    {
                        "role": "user",
                        "content": f"""以下の検索クエリで醸造所の公式情報を検索してください。
検索クエリ: {query}

検索結果から、麦芽・ホップ・水・副原料に関する醸造所の公式トピックを抽出し、
以下のJSON形式で回答してください（最大5件）:

```json
[
  {{
    "title": "記事タイトル（英語）",
    "brewery": "醸造所名または組織名",
    "country": "国名",
    "category": "麦芽/ホップ/水/副原料",
    "url": "記事URL",
    "summary_en": "英語での要約（200字程度）",
    "estimated_popularity": 1-10の人気スコア（推定アクセス数に基づく）
  }}
]
```

公式サイト（ brewery の .com, .co.jp, .org, .eu サイト）の情報のみ含めてください。
ブログや個人サイトは除外してください。""",
                    }
                ],
            )

            # レスポンスからJSON抽出
            for block in response.content:
                if block.type == "text":
                    text = block.text
                    # JSON部分を抽出
                    if "```json" in text:
                        json_str = text.split("```json")[1].split("```")[0].strip()
                        try:
                            articles = json.loads(json_str)
                            all_articles.extend(articles)
                            print(f"  ✅ {len(articles)}件取得: {query[:50]}...")
                        except json.JSONDecodeError:
                            print(f"  ⚠️ JSON解析エラー: {query[:50]}...")

        except Exception as e:
            print(f"  ❌ 検索エラー ({query[:50]}...): {e}")

    return all_articles


def rank_and_deduplicate(articles: list[dict]) -> list[dict]:
    """記事をランキングし、重複を除去してTop10を返す"""
    seen_urls = set()
    unique_articles = []

    for article in articles:
        url = article.get("url", "")
        title = article.get("title", "")
        key = url or title
        if key and key not in seen_urls:
            seen_urls.add(key)
            unique_articles.append(article)

    # 人気スコアで降順ソート
    unique_articles.sort(
        key=lambda x: x.get("estimated_popularity", 0), reverse=True
    )

    return unique_articles[:10]


def translate_and_summarize(client: anthropic.Anthropic, articles: list[dict]) -> list[dict]:
    """記事を日本語に翻訳し、500文字程度に要約する"""
    print("🌐 日本語翻訳・要約中...")

    articles_json = json.dumps(articles, ensure_ascii=False, indent=2)

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        messages=[
            {
                "role": "user",
                "content": f"""以下のビール醸造所ニュース記事リストを、日本語マガジン用に翻訳・要約してください。

入力データ:
{articles_json}

各記事について以下の情報を日本語で作成してください:
1. title_ja: 記事タイトルの日本語訳（わかりやすく）
2. brewery_ja: 醸造所名（可能であれば日本語表記も追加）
3. category_ja: カテゴリ（麦芽/ホップ/水/副原料）
4. summary_ja: 日本語要約（正確に500文字程度、醸造の専門知識を活かした解説）
5. highlight: この記事の最も重要なポイント（50文字以内）

JSON形式で回答してください:
```json
[
  {{
    "rank": 順位（1から）,
    "title_ja": "日本語タイトル",
    "title_en": "元の英語タイトル",
    "brewery": "醸造所名",
    "brewery_ja": "醸造所名（日本語）",
    "country": "国名",
    "country_ja": "国名（日本語）",
    "category": "英語カテゴリ",
    "category_ja": "日本語カテゴリ",
    "url": "元記事URL",
    "summary_ja": "500文字程度の日本語要約",
    "highlight": "ハイライト（50文字以内）",
    "estimated_popularity": 人気スコア
  }}
]
```

醸造の専門用語（IBU、EBC、SRM、OG、FG、α酸、β酸、コーヒー風味のモルトなど）は適切に使用してください。""",
            }
        ],
    )

    translated_articles = []
    for block in response.content:
        if block.type == "text":
            text = block.text
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
                try:
                    translated_articles = json.loads(json_str)
                    print(f"  ✅ {len(translated_articles)}件の翻訳完了")
                except json.JSONDecodeError as e:
                    print(f"  ❌ 翻訳JSON解析エラー: {e}")

    return translated_articles


def generate_html_magazine(articles: list[dict], date_str: str) -> str:
    """HTMLマガジンを生成する"""

    category_colors = {
        "麦芽": "#8B6914",
        "ホップ": "#4A7C2F",
        "水": "#1E6B9E",
        "副原料": "#9B4E9E",
        "malt": "#8B6914",
        "hops": "#4A7C2F",
        "water": "#1E6B9E",
        "adjunct": "#9B4E9E",
    }

    category_icons = {
        "麦芽": "🌾",
        "ホップ": "🌿",
        "水": "💧",
        "副原料": "🌽",
    }

    articles_html = ""
    for i, article in enumerate(articles, 1):
        cat = article.get("category_ja", article.get("category", ""))
        color = category_colors.get(cat, "#666")
        icon = category_icons.get(cat, "🍺")
        pop = article.get("estimated_popularity", 5)
        stars = "⭐" * min(int(pop / 2), 5)

        # 本文を段落に分割（改行2つで分割）
        summary_paragraphs = article.get('summary_ja', '').replace('\\n', '\n').split('\n\n')
        summary_html = ''.join(f'<p class="summary">{p.strip()}</p>' for p in summary_paragraphs if p.strip())

        analysis = article.get('analysis_ja', '')

        articles_html += f"""
        <article class="article-card" style="border-left: 4px solid {color};">
            <div class="article-header">
                <span class="rank">#{i}</span>
                <span class="category" style="background:{color};">{icon} {cat}</span>
                <span class="popularity">{stars}</span>
            </div>
            <h2 class="article-title">{article.get('title_ja', article.get('title_en', ''))}</h2>
            <div class="article-meta">
                <span class="brewery">🏭 {article.get('brewery_ja', article.get('brewery', ''))}</span>
                <span class="country">🌍 {article.get('country_ja', article.get('country', ''))}</span>
            </div>
            <div class="highlight">💡 {article.get('highlight', '')}</div>
            <div class="summary-body">
                {summary_html if summary_html else f'<p class="summary">{article.get("summary_ja","")}</p>'}
            </div>
            <div class="analysis-box">
                <div class="analysis-title">🔍 編集部の考察</div>
                <p class="analysis-text">{analysis}</p>
            </div>
            <div class="article-footer">
                <a href="{article.get('url', '#')}" target="_blank" rel="noopener" class="source-link">
                    📰 オリジナル記事を読む
                </a>
            </div>
        </article>
        """

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🍺 BREW DAILY - {date_str}</title>
    <style>
        :root {{
            --beer-amber: #F5A623;
            --beer-dark: #3D2B1F;
            --beer-cream: #FFF8E7;
            --beer-foam: #FEFAE0;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Hiragino Sans', 'Meiryo', 'Yu Gothic', sans-serif;
            background: var(--beer-cream);
            color: var(--beer-dark);
            line-height: 1.8;
        }}

        header {{
            background: linear-gradient(135deg, var(--beer-dark) 0%, #6B3A2A 100%);
            color: white;
            padding: 2rem;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}

        .magazine-title {{
            font-size: 3rem;
            font-weight: 900;
            letter-spacing: 0.1em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        }}

        .magazine-subtitle {{
            font-size: 1.1rem;
            color: var(--beer-amber);
            margin-top: 0.5rem;
            letter-spacing: 0.05em;
        }}

        .magazine-date {{
            font-size: 0.9rem;
            color: #ccc;
            margin-top: 0.3rem;
        }}

        .categories-legend {{
            display: flex;
            justify-content: center;
            gap: 1rem;
            padding: 1rem 2rem;
            background: var(--beer-foam);
            flex-wrap: wrap;
            border-bottom: 2px solid var(--beer-amber);
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 0.4rem;
            font-size: 0.85rem;
        }}

        .legend-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
        }}

        main {{
            max-width: 900px;
            margin: 2rem auto;
            padding: 0 1rem;
        }}

        .section-title {{
            font-size: 1.5rem;
            font-weight: bold;
            color: var(--beer-dark);
            margin-bottom: 1.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 3px solid var(--beer-amber);
        }}

        .article-card {{
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .article-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }}

        .article-header {{
            display: flex;
            align-items: center;
            gap: 0.8rem;
            margin-bottom: 0.8rem;
        }}

        .rank {{
            font-size: 1.5rem;
            font-weight: 900;
            color: var(--beer-amber);
            min-width: 2.5rem;
        }}

        .category {{
            color: white;
            padding: 0.2rem 0.8rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
        }}

        .popularity {{
            margin-left: auto;
            font-size: 0.85rem;
        }}

        .article-title {{
            font-size: 1.15rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
            color: var(--beer-dark);
            line-height: 1.5;
        }}

        .article-meta {{
            display: flex;
            gap: 1.5rem;
            font-size: 0.85rem;
            color: #666;
            margin-bottom: 0.8rem;
        }}

        .highlight {{
            background: #FFF3CD;
            border: 1px solid #FFD700;
            border-radius: 4px;
            padding: 0.5rem 0.8rem;
            font-size: 0.88rem;
            font-weight: bold;
            margin-bottom: 0.8rem;
            color: #856404;
        }}

        .summary {{
            font-size: 0.92rem;
            line-height: 1.9;
            color: #333;
            text-align: justify;
        }}

        .article-footer {{
            margin-top: 1rem;
            padding-top: 0.8rem;
            border-top: 1px solid #eee;
        }}

        .summary-body p + p {{
            margin-top: 1em;
        }}

        .analysis-box {{
            background: #F0F7FF;
            border: 1px solid #B8D4F0;
            border-radius: 6px;
            padding: 1rem 1.2rem;
            margin-top: 1.2rem;
        }}

        .analysis-title {{
            font-weight: bold;
            color: #1E6B9E;
            font-size: 0.95rem;
            margin-bottom: 0.5rem;
        }}

        .analysis-text {{
            font-size: 0.92rem;
            line-height: 1.9;
            color: #2a2a3a;
        }}

        .source-link {{
            color: #1E6B9E;
            text-decoration: none;
            font-size: 0.85rem;
        }}

        .source-link:hover {{
            text-decoration: underline;
        }}

        footer {{
            text-align: center;
            padding: 2rem;
            background: var(--beer-dark);
            color: #aaa;
            font-size: 0.85rem;
            margin-top: 3rem;
        }}

        footer strong {{
            color: var(--beer-amber);
        }}

        @media (max-width: 600px) {{
            .magazine-title {{ font-size: 2rem; }}
            .article-meta {{ flex-direction: column; gap: 0.3rem; }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="magazine-title">🍺 BREW DAILY</div>
        <div class="magazine-subtitle">世界のブルワリー最新情報マガジン</div>
        <div class="magazine-date">📅 {date_str} 発行 | 麦芽・ホップ・水・副原料 最新トピック Top 10</div>
    </header>

    <div class="categories-legend">
        <div class="legend-item">
            <span class="legend-dot" style="background:#8B6914;"></span>
            🌾 麦芽（Malt）
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background:#4A7C2F;"></span>
            🌿 ホップ（Hops）
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background:#1E6B9E;"></span>
            💧 水（Water）
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background:#9B4E9E;"></span>
            🌽 副原料（Adjunct）
        </div>
    </div>

    <main>
        <h2 class="section-title">📊 今日のランキング Top 10</h2>
        {articles_html if articles_html else '<p style="text-align:center; padding:2rem; color:#666;">本日の記事を取得中にエラーが発生しました。</p>'}
    </main>

    <footer>
        <p><strong>BREW DAILY</strong> は世界中の醸造所公式情報を自動収集し、AI が日本語に翻訳・要約した独自マガジンです。</p>
        <p style="margin-top:0.5rem;">Generated by Claude AI | Powered by Anthropic | {date_str}</p>
    </footer>
</body>
</html>"""

    return html


def run_with_demo_data(client: anthropic.Anthropic) -> list[dict]:
    """デモ用サンプルデータを生成（5件ずつ2回に分けてJSON解析エラーを回避）"""
    print("📝 Claude にデモ記事を生成させています...")

    all_articles = []

    for batch, (category_set, ranks) in enumerate([
        ("麦芽(2件)・ホップ(2件)・水(1件)", "1から5"),
        ("ホップ(1件)・水(1件)・副原料(2件)・麦芽(1件)", "6から10"),
    ]):
        prompt = f"""世界の醸造所の麦芽・ホップ・水・副原料に関する2025年のニュース記事を
{category_set}の内訳で5件、JSON配列で作成してください。
rankは{ranks}。

必ず以下の形式のみで回答してください（説明文不要）:
[
  {{
    "rank": 数字,
    "title_ja": "タイトル",
    "title_en": "Title",
    "brewery": "Brewery Name",
    "brewery_ja": "醸造所名",
    "country": "Country",
    "country_ja": "国名",
    "category_ja": "麦芽またはホップまたは水または副原料",
    "url": "https://brewery.com/news",
    "summary_ja": "3000文字程度の詳細な記事本文。背景・技術的詳細・業界への影響・今後の展望を含む。醸造専門用語を積極的に使用すること。",
    "analysis_ja": "500文字程度の考察。この記事がビール業界・消費者・日本市場に与える影響や意義を専門的視点から分析すること。",
    "highlight": "重要ポイント40文字以内",
    "estimated_popularity": 7
  }}
]"""

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )

            for block in response.content:
                if block.type == "text":
                    text = block.text.strip()
                    # JSON配列を抽出
                    if "[" in text:
                        start = text.index("[")
                        end = text.rindex("]") + 1
                        json_str = text[start:end]
                        try:
                            batch_articles = json.loads(json_str)
                            all_articles.extend(batch_articles)
                            print(f"  ✅ バッチ{batch+1}: {len(batch_articles)}件生成完了")
                        except json.JSONDecodeError as e:
                            print(f"  ⚠️ バッチ{batch+1} JSON修復を試みます...")
                            # 壊れたJSONを修復して再試行
                            import re
                            json_str = re.sub(r',\s*}', '}', json_str)
                            json_str = re.sub(r',\s*]', ']', json_str)
                            try:
                                batch_articles = json.loads(json_str)
                                all_articles.extend(batch_articles)
                                print(f"  ✅ バッチ{batch+1}: 修復成功 {len(batch_articles)}件")
                            except Exception:
                                print(f"  ❌ バッチ{batch+1}: 解析失敗、スキップ")
        except Exception as e:
            print(f"  ❌ バッチ{batch+1} APIエラー: {e}")

    # 取得できなかった場合はハードコードのサンプルを使用
    if not all_articles:
        print("  📋 サンプルデータを使用します")
        all_articles = _get_sample_articles()

    print(f"  ✅ 合計 {len(all_articles)}件のデモ記事生成完了")
    return all_articles[:10]


def _get_sample_articles() -> list[dict]:
    """フォールバック用サンプル記事"""
    return [
        {
            "rank": 1, "title_ja": "シエラネバダが革新的な新品種クリスタル麦芽「Aurora 120L」を正式発表",
            "title_en": "Sierra Nevada Officially Announces Innovative New Crystal Malt 'Aurora 120L'",
            "brewery": "Sierra Nevada Brewing", "brewery_ja": "シエラネバダ・ブルーイング",
            "country": "USA", "country_ja": "アメリカ", "category_ja": "麦芽",
            "url": "https://sierranevada.com/news/aurora-malt-2025", "estimated_popularity": 9,
            "summary_ja": """シエラネバダ・ブルーイングは2025年6月、自社の農業研究部門と大手モルトメーカーであるBriess Malt & Ingredientsとの5年間にわたる共同研究の成果として、新品種クリスタル麦芽「Aurora 120L」を正式に発表した。

この新品種は従来のクリスタル120に比べて糖化効率が約15%向上しており、醸造効率の大幅な改善が期待されている。開発の背景には、近年の原材料コスト上昇と持続可能な醸造への業界全体の取り組みがある。シエラネバダは2030年までにカーボンニュートラルを達成するという目標を掲げており、原料段階からの効率化がその重要な柱となっている。

Aurora 120Lの最大の特徴は、その複雑なフレーバープロファイルにある。ローストの色度（EBC換算で約290〜310）は従来品とほぼ同等でありながら、キャラメルのトフィーノートに加えて、ほのかなバニラやダークチェリーのニュアンスが加わっている。これはモルティング工程での温度プロファイルを精密にコントロールすることで、メイラード反応の進行を最適化した結果である。

糖組成の分析では、マルトース比率が従来品より約8%高く、発酵性糖の割合が増加していることが確認されている。これにより、同じ麦芽使用量でも最終的なアルコール度数がわずかに高くなる傾向があり、レシピ設計時には注意が必要だとシエラネバダの醸造チームは警告している。

適用スタイルとしては、IPAやAmber Ale、Red Aleなどに特に適しているとされているが、シエラネバダの試験醸造ではベルジャンダブルやバーレーワインにも優れた結果をもたらしたという。同社のヘッドブリュワーであるBrian Grossman氏は「Aurora 120Lは私たちのパレスト・エールからエクストリームビールまで、幅広いラインナップに革命をもたらす可能性がある」とコメントしている。

現在、Aurora 120Lはシエラネバダの直営醸造所での限定的な使用段階にあり、2026年春から一般醸造所向けの商業供給を開始する予定だ。初年度の供給量は限定的で、優先的にクラフトブルワリー向けに割り当てられる見通しである。価格は従来のCrystal 120と比較して約12%高めに設定される予定だが、糖化効率の向上を考慮すると実質的なコストパフォーマンスは同等以上になると試算されている。""",
            "analysis_ja": "Aurora 120Lの登場は、クラフトビール業界における「高品質原料への投資」というトレンドを象徴している。糖化効率15%向上は一見地味に見えるが、年間生産量が数千バレルに達する醸造所では大きなコスト削減につながる。日本市場では、地ビールブームを背景に国産クラフトブルワリーが急増しており、このような高性能麦芽への需要は今後確実に高まると予想される。特に輸入原料への依存度が高い日本の醸造所にとって、効率化と品質向上を同時に達成できる素材は喉から手が出るほど欲しい存在だ。国内モルトメーカーが類似品を開発するきっかけになる可能性も高く、業界全体の技術革新を促す触媒になりうる。",
            "highlight": "糖化効率15%向上・トフィー＆バニラの複雑な風味"
        },
        {
            "rank": 2, "title_ja": "2025年ドイツ・ハラタウ産ホップ収穫レポート：α酸6.2%の高品質年",
            "title_en": "2025 Hallertau Hop Harvest Report: High Quality Year with 6.2% Alpha Acid",
            "brewery": "Weihenstephan", "brewery_ja": "ヴァイエンシュテファン醸造・農業大学",
            "country": "Germany", "country_ja": "ドイツ", "category_ja": "ホップ",
            "url": "https://weihenstephan.de/hop-harvest-2025", "estimated_popularity": 8,
            "summary_ja": "ドイツ・バイエルン州のハラタウ地方から、2025年ホップ収穫に関する公式レポートが発表された。ヴァイエンシュテファン醸造・農業大学の研究チームと地域ホップ農家組合が共同でまとめた今年の収穫報告によると、品質・収量ともに近年で最高水準を記録したという。\n\nα酸含有量の平均値は6.2%を記録し、過去5年平均の5.7%を大きく上回った。特にハラタウトラディション種では最高7.1%を記録した圃場もあり、例年より香り成分も豊富であることが分析データで示されている。主要アロマ成分であるリナロールの含有量は前年比23%増で、フローラルかつスパイシーな香りプロファイルが際立っている。\n\n今年の好結果の主な要因として、6〜8月の気候条件が理想的だったことが挙げられる。降水量が平年比90%と適度で日照時間は平年比110%を記録し、ホップの成熟に最適な条件が整った。また、地域農家が昨年から導入した精密農業技術（ドローンによる生育状況モニタリングと土壌センサーを活用した灌漑制御）が功を奏したとの見解も示されている。\n\n収穫量は前年比で約8%増加し、ハラタウ地方全体で約2,200トンに達した。この量はドイツ国内需要をほぼ賄えるほどの規模であり、一部は輸出に回される見込みだ。日本への輸出割当量も増加する方向で交渉が進んでいると関係者は述べている。\n\n品種別では、ペルレ（Perle）が最も多く生産されており、全体の約35%を占める。続いてハラタウトラディション（22%）、マグナム（18%）と続く。近年需要が高まっているアロマホップのハラタウブラン（Hallertau Blanc）は昨年比で栽培面積が15%増加し、クラフトビール市場での引き合いの強さを反映している。\n\nヴァイエンシュテファンのホップ研究所所長Dr.クラウス・バウアー氏は「2025年は1990年代の黄金期に匹敵するほどの優れた収穫年だ。特にアロマホップの品質は過去20年で最高レベルにある」と評価している。",
            "analysis_ja": "ハラタウ産ホップの高品質な収穫は、世界中の醸造所にとって朗報だ。特に日照時間の増加による天然のα酸・アロマ成分の増加は、醸造コストを抑えながら風味豊かなビールを生産できることを意味する。日本のクラフトビール市場では輸入ホップへの依存度が高いため、品質向上と供給量増加は直接的なメリットとなる。一方で、気候変動の影響でこうした「当たり年」が不規則になっているという懸念もある。精密農業技術の導入が安定供給への鍵となっており、日本のホップ産地である岩手や北海道の農家も参考にすべき事例だ。",
            "highlight": "α酸6.2%・リナロール23%増の過去最高品質"
        },
        {
            "rank": 3, "title_ja": "アサヒビールが仕込み水ミネラル精密制御システム「AquaControl Pro」を公開",
            "title_en": "Asahi Reveals Precision Mineral Control System 'AquaControl Pro' for Brewing Water",
            "brewery": "Asahi Breweries", "brewery_ja": "アサヒビール株式会社",
            "country": "Japan", "country_ja": "日本", "category_ja": "水",
            "url": "https://asahibeer.co.jp/news/aquacontrol-2025", "estimated_popularity": 8,
            "summary_ja": "アサヒビールは2025年5月の株主総会において、独自開発の仕込み水ミネラル精密制御システム「AquaControl Pro」の詳細を初めて公開した。このシステムは、スーパードライをはじめとする主力製品の味の一貫性を科学的に担保するために5年以上の歳月をかけて開発されたものだ。\n\nAquaControl Proの核心は、リアルタイムイオン測定センサーと自動添加装置を組み合わせた「動的ミネラル補正技術」にある。仕込み水のカルシウムイオン（Ca²⁺）、マグネシウムイオン（Mg²⁺）、重炭酸イオン（HCO₃⁻）、硫酸イオン（SO₄²⁻）、塩化物イオン（Cl⁻）の5項目を0.1ppm単位でリアルタイム測定し、目標プロファイルとの差分を毎秒計算。必要に応じて食品グレードの各種ミネラル塩を自動的に添加する仕組みだ。\n\nスーパードライに求められる水質プロファイルは、カルシウム50〜60ppm、マグネシウム10〜15ppm、硫酸塩80〜100ppm、塩化物30〜40ppmとされており、これを全国8か所の工場で均一に再現することが長年の課題だった。地域によって原水の水質が大きく異なるため、従来は手動による添加調整に依存していたが、AquaControl Proの導入により全工場で±2ppm以内の精度を達成したという。\n\n同社の研究開発部門によると、ミネラルバランスの精密制御はビールの味わいに複数の経路で影響する。カルシウムはプロテインの沈殿を促進してビールの透明度を向上させ、酵母の健全な発酵を助ける。硫酸塩はホップの苦味をシャープで切れのある印象に変え、塩化物はモルトの甘みと丸みを引き出す。これらの相互作用を最適化することが「辛口」というスーパードライのアイデンティティを守ることにつながる。\n\n同システムはすでに国内全工場への導入が完了しており、海外のアサヒ・グループ工場への展開も2026年を目標に進められている。将来的にはAIを活用した予測補正機能の追加も検討されており、季節や原水の変動を事前に予測して補正するシステムへの進化を目指している。",
            "analysis_ja": "アサヒの「AquaControl Pro」は、大手ビールメーカーが品質管理にいかにテクノロジーを活用しているかを示す好例だ。±2ppmという精度での水質制御は、研究室レベルでは当然だが、大規模商業生産で実現したのは画期的と言える。日本のクラフトビール醸造所では水質管理が後回しにされがちだが、本事例は水がビールの品質に与える影響の大きさを改めて示している。中小規模の醸造所がこのような高精度システムを導入するのはコスト面で困難だが、廉価版の水質モニタリングツールの普及が業界全体の底上げにつながることが期待される。",
            "highlight": "全工場で±2ppmの精度を実現する水質制御"
        },
        {
            "rank": 4, "title_ja": "BrewDogがオーツ麦30%使用ヘイジーIPA「Velvet Thunder」のレシピと製法を完全公開",
            "title_en": "BrewDog Fully Discloses Recipe and Process for Oat-Heavy Hazy IPA 'Velvet Thunder'",
            "brewery": "BrewDog", "brewery_ja": "ブリュードッグ",
            "country": "Scotland", "country_ja": "スコットランド", "category_ja": "副原料",
            "url": "https://brewdog.com/beer/velvet-thunder-recipe", "estimated_popularity": 7,
            "summary_ja": "スコットランドのクラフトブルワリー・ブリュードッグは、同社のオープンソース醸造哲学の一環として、ヘイジーIPA「Velvet Thunder」の完全なレシピと製法をウェブサイト上で無償公開した。ロールドオーツを全穀物比の30%使用するという大胆な配合が最大の特徴で、この比率はニューイングランドスタイルIPAの中でも特に高い部類に入る。\n\n穀物構成はペールモルト55%、ロールドオーツ30%、小麦モルト15%。オーツ麦はフレーク状に加工されたロールドオーツを使用し、糊化しやすいよう先にマッシュタブに投入するプロテインレスト（50℃・15分）を挟む二段階マッシング法を採用している。この工程がオーツ由来のベータグルカンを適度に分解し、過度な粘性を防ぎながらシルキーなマウスフィールを生み出す鍵となっている。\n\n苦味は20IBUと抑えめに設定されており、ホップはシトラ、モザイク、ネルソンソーヴィンの3品種をドライホッピングに集中投入する。煮沸中のホップ添加は最小限にとどめ、ホップアロマの揮発を防ぐことでジューシーで香り豊かなプロファイルを実現している。発酵後のドライホッピングは2段階で行い、1回目（7℃・72時間）でフルーティーな香りを定着させ、2回目（20℃・24時間）でより複雑なアロマを引き出す独自プロセスを採用している。\n\n酵母はロンドンエール酵母系統を使用し、発酵温度は20〜22℃で管理。オーツ麦由来のタンパク質と酵母が相互作用することで生まれる白濁した外観は、スタイルの重要な要素であると同社は説明している。OG（初期比重）は1.068、FG（最終比重）は1.016で、アルコール度数は6.8%に仕上がる。\n\nブリュードッグのオープンソース哲学はクラフトビール業界に大きな影響を与えてきた。公開されたレシピは世界中のホームブルワーや小規模醸造所が参考にできるよう、バッチサイズ別の穀物量・ホップ量・水量の計算式も含まれており、醸造コミュニティからの反響は公開24時間で10万件を超えるアクセスを記録したという。",
            "analysis_ja": "ブリュードッグのオープンソース戦略は、クラフトビール業界独特のコミュニティ文化を体現している。レシピ公開はビジネス的には一見リスクに見えるが、ブランド認知度と信頼性の向上というリターンが大きい。オーツ麦30%という高配合は日本のホームブルワーにとっても再現性が高く、国内クラフトブルワリーの参考事例になる可能性が高い。日本ではヘイジースタイルの人気が急上昇しており、このような詳細なレシピ公開は国内醸造技術の底上げにつながると期待される。オーツ麦は農家との直接契約で安定調達できる副原料であり、国産素材活用の観点からも注目に値する。",
            "highlight": "オーツ麦30%配合レシピを業界初の完全無償公開"
        },
        {
            "rank": 5, "title_ja": "キリンビールが北海道農家と次世代大麦「きたのほし2号」の長期栽培契約を締結",
            "title_en": "Kirin Brewery Signs Long-Term Contract for Next-Gen Barley 'Kitanohoshi No.2' with Hokkaido Farmers",
            "brewery": "Kirin Brewery", "brewery_ja": "キリンビール株式会社",
            "country": "Japan", "country_ja": "日本", "category_ja": "麦芽",
            "url": "https://kirin.co.jp/news/barley-contract-2025", "estimated_popularity": 7,
            "summary_ja": "キリンビールは2025年6月、北海道上川地方の大麦農家15戸と、新品種大麦「きたのほし2号」の長期栽培・供給契約（10年間）を締結したと発表した。この新品種は農研機構北海道農業研究センターとキリングループが共同で10年以上かけて育種した成果であり、国産麦芽の品質向上と安定供給体制の強化を目的としている。\n\nきたのほし2号の主な特徴は三点ある。第一に、縞萎縮病やうどんこ病に対する高い抵抗性を持つことで、農薬使用量を従来品種比で約40%削減できる。これはコスト削減だけでなく、環境負荷低減という観点からも重要な意義を持つ。第二に、収量が従来の主力品種「はるしずく」と比べて約20%増加しており、同面積での生産効率が大幅に向上する。第三に、麦芽の品質指標であるコルバッハ値（タンパク質溶解度の指標）が最適範囲の38〜42%に安定しやすく、安定した醸造特性が得られる。\n\n契約農家の代表である上川農業協同組合の田中誠一組合長は「新品種の導入により、農家の経営安定と品質向上が同時に実現できる。キリンとの長期契約があることで、安心して設備投資や農地拡大に取り組める」とコメントしている。\n\nキリンビールは契約農家に対して、専用の播種機械のリースプログラムと技術指導（年4回の巡回指導）を提供するほか、収穫後の品質検査と精算まで一貫してサポートする体制を整える。2026年産から商業生産を本格開始し、2028年には同社の国産麦芽使用比率を現在の65%から75%へ引き上げる目標を掲げている。\n\n日本のビールメーカーにとって国産麦芽の安定確保は重要な課題だ。輸入大麦の価格変動リスクや為替の影響を軽減するためにも、国産原料の比率を高める動きは今後さらに加速することが予想される。",
            "analysis_ja": "キリンの長期栽培契約は、食料安全保障という観点から非常に戦略的な動きだ。円安や海外穀物価格の高騰が続く中、国産原料の安定調達は競争優位性の源泉となる。農薬使用量40%削減は環境価値だけでなく、消費者へのサステナビリティアピールにも直結する。一方で、単一品種への依存度が高まるリスクも考慮が必要で、病気や気候変動による不作が大きなダメージにつながりかねない。日本のビール業界全体として、国産麦芽の品質と供給量を高める取り組みは評価されるべきであり、この事例が他のメーカーの後押しになることが期待される。",
            "highlight": "病害抵抗性強化・収量20%増の国産新品種"
        },
        {
            "rank": 6, "title_ja": "ハイネケンがオランダに世界初の太陽光100%ホップ農場「Green Cone Farm」を開設",
            "title_en": "Heineken Opens World's First 100% Solar-Powered Hop Farm 'Green Cone Farm' in Netherlands",
            "brewery": "Heineken", "brewery_ja": "ハイネケン・ジャパン",
            "country": "Netherlands", "country_ja": "オランダ", "category_ja": "ホップ",
            "url": "https://heineken.com/sustainability/green-cone-farm", "estimated_popularity": 8,
            "summary_ja": "ハイネケンは2025年5月、オランダ・ゼーラント州に世界初の太陽光発電100%駆動のホップ農場「Green Cone Farm」を正式開設した。5ヘクタールの農地に設置された1,200枚の太陽光パネルが農場のすべての電力需要を賄い、余剰電力は地域電力網に供給するという革新的なモデルだ。\n\nGreen Cone Farmで栽培するホップ品種は主に「Hallertau Blanc」と「Mandarina Bavaria」の2種類で、柑橘系アロマが豊富なホップとして知られる。農場では精密農業技術を全面的に採用しており、土壌センサー・気象ステーション・ドローンモニタリングシステムが24時間稼働している。これにより灌漑水の使用量を従来農法と比べて40%、化学肥料の使用量を35%それぞれ削減することに成功した。\n\nCO2排出量の試算では、従来の農法と比較して年間約280トンの削減が見込まれており、ハイネケン全体の排出量削減目標（2030年までに2018年比で30%削減）に向けた重要な取り組みと位置づけられている。農場で収穫されたホップは全量ハイネケンの欧州工場へ供給され、環境負荷の低い「グリーンホップ」として特別なトレーサビリティラベルを付けて管理される。\n\nハイネケンのサステナビリティ担当副社長ルシア・フェルハーヘン氏は「ビール醸造において原料調達段階の環境負荷を下げることが最も重要な課題の一つだ。Green Cone Farmはその解答の一つであり、今後10年以内に同様の農場をヨーロッパ全土に拡大したい」と語った。\n\nこの農場モデルに対する業界の関心は高く、すでにカールスバーグ、アサヒ・ヨーロッパなどの競合他社から農場見学の申し込みが相次いでいるという。2026年にはオランダ政府の農業振興プログラムとの連携も予定されており、補助金活用によるコスト低減も見込まれている。",
            "analysis_ja": "ハイネケンのGreen Cone Farmは、ビール産業全体がサステナビリティを競争軸として位置づけ始めた時代の象徴だ。太陽光100%という取り組みはPR効果も高く、ESG投資家からの評価向上にも寄与する。日本でも「環境に配慮したビール」への消費者関心は高まっており、こうした取り組みが商品ブランディングに直結する時代が来ている。一方で、太陽光発電農場の設置コストや天候依存リスクなど課題もある。日本のホップ産地（岩手、秋田）での同様モデルの検討は、農家の収益安定と環境配慮の両立という点で意義深い。",
            "highlight": "太陽光100%・水使用量40%削減の環境型農場"
        },
        {
            "rank": 7, "title_ja": "サッポロビールが「超軟水リバイバル製法」を発表、硬度8の水で醸造する限定ラガー",
            "title_en": "Sapporo Brewery Announces 'Ultra-Soft Water Revival Method', Limited Lager Brewed with Hardness 8 Water",
            "brewery": "Sapporo Breweries", "brewery_ja": "サッポロビール株式会社",
            "country": "Japan", "country_ja": "日本", "category_ja": "水",
            "url": "https://sapporobeer.jp/news/ultra-soft-revival-2025", "estimated_popularity": 7,
            "summary_ja": "サッポロビールは2025年6月、明治時代の創業当初から続く「北海道軟水醸造」の伝統を現代技術で復活させた「超軟水リバイバル製法」と、これを用いた限定醸造ラガー「SAPPORO GENESIS」の発売を発表した。\n\n超軟水リバイバル製法の核心は、硬度8mg/L（ドイツ硬度0.45°dH）という極めて低い硬度の水を仕込み水として使用することにある。通常の商業醸造では硬度50〜150mg/Lの水を使用するが、サッポロは北海道大雪山系の伏流水をナノフィルトレーション処理することで、ほぼ純水に近い超軟水を製造している。\n\n超軟水醸造の最大の特徴は、モルトの甘みとデンプン由来の旨味成分が水のミネラル干渉なく最大限に表現されることにある。硫酸塩やカルシウムが少ない環境では、ホップの苦味がよりなめらかに感じられ、後味のクリーンさが際立つ。一方で醸造上の課題もあり、カルシウムが少ない環境では酵母の凝集性が下がり、澱引きが難しくなる。この問題をサッポロは、特殊な低温長期熟成プロセス（0℃・90日間）と遠心分離機の組み合わせで解決した。\n\nSAPPORO GENESISは道内限定1万本の限定醸造で、価格は350ml缶で税込450円（通常品の約2倍）に設定される。発売は2025年9月を予定しており、すでに予約受付が始まっている。同社マーケティング部の渡辺啓二部長は「この製品は私たちの創業の精神へのオマージュであり、水という最も基本的な原料がいかにビールの個性を決定するかを示す実験でもある」とコメントしている。\n\n今後は超軟水醸造のノウハウを蓄積し、2027年を目標に超軟水醸造ラインを恵比寿工場に新設する計画も明らかにした。",
            "analysis_ja": "サッポロの「超軟水リバイバル製法」は、歴史とテクノロジーを融合させたブランドストーリーの好事例だ。硬度8という極限の軟水は技術的な挑戦であると同時に、北海道というテロワールを最大限に活かす哲学でもある。限定1万本・450円という高価格設定は、プレミアム化戦略の一環として理にかなっている。ビールの「水の個性」を前面に打ち出すこのアプローチは、ウイスキーのシングルモルト文化に近い発想であり、ビールの高付加価値化に向けた重要なヒントを与えている。日本の水道水文化を背景に、水質へのこだわりは国内消費者に刺さりやすいメッセージだ。",
            "highlight": "硬度8の超軟水×90日熟成の限定ラガー"
        },
        {
            "rank": 8, "title_ja": "ニューベルギーがコロラド産リンゴとワイルド酵母を使用したサワーエール「Orchard Funk」を発売",
            "title_en": "New Belgium Releases Sour Ale 'Orchard Funk' Using Colorado Apples and Wild Yeast",
            "brewery": "New Belgium Brewing", "brewery_ja": "ニューベルギー・ブルーイング",
            "country": "USA", "country_ja": "アメリカ", "category_ja": "副原料",
            "url": "https://newbelgium.com/beer/orchard-funk", "estimated_popularity": 6,
            "summary_ja": "コロラド州フォートコリンズのニューベルギー・ブルーイングは、地元コロラド産リンゴを副原料とした自然発酵サワーエール「Orchard Funk」を2025年夏季限定で発売する。同社の野生酵母発酵プログラム「Foeder Experiment Series」の第7弾として位置づけられており、コロラド農業界との連携強化を体現した製品だ。\n\nOrchard Funkの醸造プロセスは複雑で、約18ヶ月の歳月をかけて醸造される。まずベースモルト70%・小麦モルト30%の醸造液を仕込み、これをオーク製のフーダー（foeder、大型木桶）に移してブレタノマイセス酵母と乳酸菌による自然発酵を行う。フーダー発酵期間は6ヶ月で、この過程でほのかなバーンヤード臭（馬小屋様の香り）と複雑な酸味が形成される。\n\n次に、コロラド州グランドジャンクション近郊の契約農園で収穫されたゴールデンデリシャスとフジのブレンドリンゴジュース（糖度12 Brix）を全体量の25%加えてブレンド発酵を行う。リンゴ由来のマリン酸がビール中の乳酸と相互作用することで、柔らかく果実味豊かな酸味が生まれる。最終的な酸度はpH3.4、乳酸濃度は約1.2g/Lに調整される。\n\nフレーバープロファイルは、グリーンアップル・スウィートチェリー・レモングラスの香りに、わずかなバニラと木の風味が重なる複雑な構成。アルコール度数は6.2%で、残糖は少なくドライな後味が特徴。フードペアリングとしては、ブルーチーズやシェーブルなどのチーズ、グリルした豚肉料理、アップルパイなどのデザートとの相性が特に良いとされている。\n\n価格は375ml瓶で9.99ドルと、同社の通常製品の約2倍の価格設定。限定5,000本での発売で、公式ウェブサイトでの予約注文が主な販売チャネルとなる。",
            "analysis_ja": "ニューベルギーのOrchard Funkは、「地産地消」とワイルド発酵というクラフトビール界の二大トレンドを掛け合わせた意欲的な製品だ。18ヶ月の熟成期間はコスト面での大きな投資であり、それを価格に反映させる強さがブランドにある。日本でもサワービールの人気が上昇しており、地元農産物を副原料とした酸味系ビールへの需要は確実に増加している。ブレタノマイセス発酵は日本では法的制限もあり難しい面があるが、乳酸菌による発酵やフルーツ副原料の活用は国内でも実現可能だ。地方のブルワリーが地域農家と連携するビジネスモデルとして参考になる。",
            "highlight": "18ヶ月熟成・コロラド産リンゴ25%配合の自然発酵"
        },
        {
            "rank": 9, "title_ja": "ドッグフィッシュ・ヘッドが古代エジプトの二条大麦を復元、3000年前のビールを限定醸造",
            "title_en": "Dogfish Head Recreates Ancient Egyptian Two-Row Barley, Brews 3,000-Year-Old Beer in Limited Edition",
            "brewery": "Dogfish Head Craft Brewery", "brewery_ja": "ドッグフィッシュ・ヘッド・クラフト・ブルワリー",
            "country": "USA", "country_ja": "アメリカ", "category_ja": "麦芽",
            "url": "https://dogfish.com/news/ancient-egyptian-malt-2025", "estimated_popularity": 6,
            "summary_ja": "デラウェア州のドッグフィッシュ・ヘッド・クラフト・ブルワリーが、ペンシルベニア大学考古学博物館との6年間にわたる共同研究の成果として、古代エジプトのビール醸造に使用されていた二条大麦（Hordeum vulgare subsp. distichon）の古代品種を現代で復元し、限定醸造ビール「Kha-Ankh（カアンク）」を発売すると発表した。\n\n研究チームはエジプトのルクソール近郊にある紀元前1350年頃の遺跡から発掘された大麦の種子からDNAを抽出・解析し、現存する在来品種の中から最も近い遺伝子プロファイルを持つエチオピア産古代大麦を特定した。この品種はモダン品種と比べてタンパク質含量が高く（14〜16%）、デンプン構造も異なるため、通常の現代的マッシング手法では糖化効率が低い。\n\n醸造プロセスの再現においては、エジプト考古学者チームの考証に基づき、現代の醸造設備と古代製法を組み合わせたハイブリッドアプローチを採用した。麦芽はナイル川流域に近い環境を模倣した砂質土壌で栽培し、手作業による脱穀・選別を経てフロアモルティング（床麦芽製法）で製麦した。ホップは使用せず、代わりにコリアンダー・シダーウッド・没薬（ミルラ）・デーツを香味付けに使用している。これらの素材はエジプトのヒエログリフに記されたビールレシピの解読に基づいて選定された。\n\n発酵にはエジプト在来の野生酵母株をベースに、現代の醸造用サッカロミセス・セレビシエと組み合わせたハイブリッド酵母を使用。発酵温度は30〜32℃と高めに設定し、古代エジプトの気候環境を再現した。仕上がりのアルコール度数は約4.5%で、やや甘く・スパイシーで・わずかにスモーキーな風味が特徴とされている。\n\n限定500本（750ml瓶）で価格は1本89ドルという超プレミアム設定で、ウェブサイト限定販売。考古学研究への寄付（1本あたり10ドル）も含まれている。",
            "analysis_ja": "ドッグフィッシュ・ヘッドの古代ビール復元プロジェクトは、クラフトビールが単なる飲料を超えて文化的・学術的価値を持つ存在になりつつあることを示している。1本89ドルという価格でも500本が即売されることは、ビールのコレクターズアイテム化という新たな市場セグメントの存在を証明している。日本でも地域の歴史・文化と結びついたビール（古代米や縄文時代の素材を使用など）への関心が高まっており、こうした「ストーリービール」は付加価値創出の重要な戦略となりうる。大学や研究機関との連携は信頼性向上にも寄与するため、日本の地方醸造所が地域大学と組む可能性も示唆している。",
            "highlight": "古代DNA解析で復元した3000年前のエジプトビール"
        },
        {
            "rank": 10, "title_ja": "カールスバーグが超臨界CO₂ホップ抽出技術でノンアル向け香り成分保持に成功",
            "title_en": "Carlsberg Successfully Preserves Hop Aroma Components for Non-Alcoholic Beer Using Supercritical CO₂ Extraction",
            "brewery": "Carlsberg Group", "brewery_ja": "カールスバーグ・グループ",
            "country": "Denmark", "country_ja": "デンマーク", "category_ja": "ホップ",
            "url": "https://carlsberg.com/research/sc-co2-hop-extraction", "estimated_popularity": 7,
            "summary_ja": "デンマークのカールスバーグ・グループは、同社のCarlsberg Research Laboratory（CRL）が開発した超臨界二酸化炭素（SC-CO₂）抽出技術を用いたホップアロマ成分保持システムの特許取得と、これを活用したノンアルコールビール新製品の開発を発表した。\n\nSC-CO₂抽出は、31.1℃・73.8気圧という臨界点を超えた状態の二酸化炭素が液体と気体の中間的な性質を持つことを利用した技術だ。通常の溶剤抽出と異なり、アロマ成分を高温・酸素暴露から守りながら選択的に抽出できるため、デリケートなモノテルペン（リナロール・ゲラニオール・ネロール）やセスキテルペン（β-ファルネセン・ハムレン）といった揮発性アロマ成分をほぼ完全な状態で保持できる。\n\n従来のノンアルコールビール醸造における最大の課題の一つが、アルコール除去プロセスによるアロマ成分の消失だった。蒸留法・逆浸透膜法いずれの脱アルコール手法においても、ホップアロマの40〜70%が失われるとされてきた。カールスバーグのシステムでは、醸造後のビールからアルコール除去を行う前にSC-CO₂でアロマ成分を分離・保存し、脱アルコール後に再添加するという「アロマレストア」プロセスを確立した。\n\n同社の試験では、開発したノンアルコールビール（アルコール度数0.5%未満）は訓練された官能評価パネルによるブラインドテストで、通常のラガービールと比較してホップアロマの印象が95%保持されていると評価された。特にシトラスやフローラルのアロマノートが顕著に改善されたとされている。\n\nこの技術はカールスバーグのノンアルコールブランド「Carlsberg 0.0」に2026年から順次採用される予定で、欧州市場から導入が始まり、2027年にはアジア市場（日本・韓国を含む）への展開も計画されている。ノンアルコールビール市場は世界的に年率15〜20%の成長を続けており、アロマ品質の向上は同市場での競争力強化に直結する。",
            "analysis_ja": "カールスバーグのSC-CO₂技術はノンアルビール市場の課題解決に向けた重要な技術革新だ。「アロマが弱い」というノンアルビール最大の弱点を克服できれば、健康志向層・妊婦・運転者など拡大を続けるノンアル消費者層への訴求力が劇的に向上する。日本のノンアル市場はアサヒ・キリン・サッポロが競争を激化させており、本技術の導入競争は不可避だ。一方、SC-CO₂設備の初期投資は億単位に上るとされており、中小醸造所には高いハードルとなる。日本のノンアルビール需要が年10%以上の成長を続けている現状を考えると、大手メーカーへの技術ライセンス交渉が加速することが予想される。",
            "highlight": "ノンアルビールのホップ香り成分を95%保持する新技術"
        },
    ]


def main():
    print("=" * 60)
    print("🍺 BREW DAILY マガジン生成開始")
    print("=" * 60)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ エラー: ANTHROPIC_API_KEY 環境変数が設定されていません")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日（%a）")
    file_date = now.strftime("%Y%m%d")

    # Step 1: 記事収集
    use_demo = "--demo" in sys.argv
    if use_demo:
        print("\n📌 デモモードで実行中（内蔵サンプルデータを使用）")
        articles = _get_sample_articles()
        print(f"  ✅ {len(articles)}件のサンプル記事を読み込みました")
    else:
        raw_articles = search_brewery_news(client)
        print(f"\n📦 収集記事数: {len(raw_articles)}件")

        if raw_articles:
            # Step 2: ランキング・重複除去
            ranked_articles = rank_and_deduplicate(raw_articles)
            print(f"🏆 ランキング後: {len(ranked_articles)}件")

            # Step 3: 翻訳・要約
            articles = translate_and_summarize(client, ranked_articles)
        else:
            print("⚠️ 記事が取得できませんでした。デモデータを使用します。")
            articles = run_with_demo_data(client)

    if not articles:
        print("❌ 記事の生成に失敗しました")
        sys.exit(1)

    # Step 4: HTML生成
    print(f"\n📰 HTMLマガジン生成中...")
    html = generate_html_magazine(articles, date_str)

    # Step 5: ファイル保存
    html_file = OUTPUT_DIR / f"brew_daily_{file_date}.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)

    # 最新版として latest.html にも保存
    latest_file = OUTPUT_DIR / "latest.html"
    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(html)

    # JSON データも保存
    json_file = OUTPUT_DIR / f"brew_daily_{file_date}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "date": now.isoformat(),
                "date_ja": date_str,
                "articles": articles,
                "count": len(articles),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("\n" + "=" * 60)
    print("✅ BREW DAILY マガジン生成完了!")
    print(f"📄 HTML: {html_file}")
    print(f"📄 最新版: {latest_file}")
    print(f"📊 JSON: {json_file}")
    print(f"📰 記事数: {len(articles)}件")
    print("=" * 60)

    # Windows の場合、ブラウザで開く
    if sys.platform == "win32":
        import subprocess
        subprocess.Popen(["start", "", str(latest_file)], shell=True)


if __name__ == "__main__":
    main()

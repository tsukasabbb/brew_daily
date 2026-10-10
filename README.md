# 🍺 BREW DAILY - 世界のブルワリー最新情報マガジン

毎朝7時に世界中の醸造所（公式情報のみ）から麦芽・ホップ・水・副原料に関するトピックを自動収集し、
アクセス数順 Top 10 をランキング、日本語に翻訳・500文字要約した独自マガジンを自動生成します。

---

## 📋 セットアップ手順

### 1. Python のインストール
[python.org](https://www.python.org/downloads/) から Python 3.10 以上をダウンロードしてインストール
（インストール時に「Add Python to PATH」にチェック）

### 2. 必要ライブラリのインストール
```
pip install anthropic
```

### 3. Anthropic API キーの設定
[Anthropic Console](https://console.anthropic.com/) でAPIキーを取得し、環境変数に設定:

**Windows（永続的に設定する方法）:**
```powershell
# PowerShell（管理者）で実行
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-xxxx...", "User")
```

---

## 🚀 使い方

### デモ実行（APIキー不要でテスト）
```powershell
cd "C:\Users\kazuy\OneDrive\デスクトップ\クロードコード\brew_daily"
python brew_magazine.py --demo
```

### 通常実行（実際のWeb検索）
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-xxxx..."
python brew_magazine.py
```

### 毎朝7時の自動実行を設定
```powershell
# 管理者権限の PowerShell で実行
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup_scheduler.ps1 -ApiKey "sk-ant-xxxx..."
```

---

## 📁 出力ファイル

| ファイル | 内容 |
|---------|------|
| `output/brew_daily_YYYYMMDD.html` | 日付付きHTMLマガジン |
| `output/latest.html` | 最新版（常に上書き） |
| `output/brew_daily_YYYYMMDD.json` | データJSON（raw） |
| `logs/brew_daily.log` | 実行ログ |

生成後、ブラウザが自動で `output/latest.html` を開きます。

---

## 🍺 マガジンの内容

### 収集対象（公式ソースのみ）
- 大手ブルワリー（Sierra Nevada, Heineken, Asahi, Kirin, Sapporo, Weihenstephan 等）
- クラフトブルワリー（Dogfish Head, BrewDog, New Belgium 等）
- 業界団体（Brewers Association, Institute of Brewing and Distilling 等）

### 収集トピック
- 🌾 **麦芽（Malt）**: 新品種、品質レポート、モルティングプロセス
- 🌿 **ホップ（Hops）**: 新品種、収穫レポート、α酸/β酸データ
- 💧 **水（Water）**: 水質管理、ミネラルプロファイル、処理技術
- 🌽 **副原料（Adjunct）**: 米・コーン・果実・スパイス、革新的配合

### ランキング基準
Claude AI が各記事の推定アクセス数・影響力・話題性を総合評価してスコアリング

---

## ⚙️ タスクスケジューラ設定（手動）

自動設定スクリプト（setup_scheduler.ps1）が失敗した場合の手動設定:

1. **タスクスケジューラ**を開く（Windowsキー → 検索）
2. 「タスクの作成」をクリック
3. **全般タブ**: 名前 = `BREW_DAILY_Magazine`
4. **トリガータブ**: 新規 → 毎日 → 開始時刻 `07:00:00`
5. **操作タブ**: 新規 → プログラム = `cmd.exe`
   引数 = `/c "C:\...\run_brew_daily.bat"`
6. **条件タブ**: 「ネットワーク接続時のみ実行」にチェック

---

## 💡 カスタマイズ

`brew_magazine.py` の先頭にある設定を編集:

```python
# 醸造所リストに追加したい場合
BREWERY_SOURCES = [
    "あなたの好みの醸造所を追加",
    ...
]

# 検索クエリの追加
SEARCH_TOPICS = [
    "your custom search topic",
    ...
]
```

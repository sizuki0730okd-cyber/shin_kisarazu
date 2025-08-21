import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import CharacterTextSplitter
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build

# --- shin_gemini_web.py から、必要なキーと関数をコピーしてくる ---

import os # osライブラリをインポート

SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY")
SEARCH_ENGINE_ID = os.environ.get("SEARCH_ENGINE_ID")

# Google検索サービスを準備
try:
    google_search_service = build("customsearch", "v1", developerKey=SEARCH_API_KEY)
except Exception as e:
    print(f"Google検索サービスの初期化に失敗しました: {e}")
    exit()

def google_search(query):
    """Google検索を実行し、上位5件のURLを返す"""
    try:
        res = google_search_service.cse().list(q=query, cx=SEARCH_ENGINE_ID, num=5).execute()
        return [item['link'] for item in res.get('items', [])]
    except Exception as e:
        print(f"Google検索に失敗 ({query}): {e}")
        return []

def scrape_website_text(url):
    """ウェブサイトからテキストを抽出する"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")
        for script_or_style in soup(["script", "style", "header", "footer", "nav"]):
            script_or_style.decompose()
        text = ' '.join(t.strip() for t in soup.body.find_all(string=True) if t.strip())
        return text
    except Exception as e:
        print(f"スクレイピングに失敗 ({url}): {e}")
        return ""

# --- ここからがメインの処理 ---

# 1. Shin君に勉強させたいトピックをリストアップ
SEARCH_TOPICS = [
    "木更津市の歴史",
    "木更津市の観光名所",
    "木更津市 祭り イベント",
    "木更津市 ご当地グルメ",
    "木更津キャッツアイ ロケ地",
    "千葉県立木更津高等学校の特色",
    "木更津高校 部活動 実績",
    "木更津高校 進路実績",
]

# 2. 各トピックについて、ウェブから情報を収集
all_scraped_text = ""
unique_links = set()

print("ウェブからの情報収集を開始します...")
for topic in SEARCH_TOPICS:
    print(f"トピック '{topic}' を検索中...")
    links = google_search(topic)
    for link in links:
        if link not in unique_links:
            unique_links.add(link)
            print(f"  -> ページを読み込み中: {link}")
            text = scrape_website_text(link)
            if text:
                all_scraped_text += f"\n\n--- 参照元: {link} ---\n{text}"

print("\n情報収集が完了しました。")

# 3. 収集したテキストを、扱いやすいように分割（チャンキング）
print("収集した情報を分割しています...")
text_splitter = CharacterTextSplitter(
    separator="\n",
    chunk_size=1000, # 1000文字ずつの塊にする
    chunk_overlap=100 # 塊の間に100文字の重なりを持たせる
)
documents = text_splitter.split_text(all_scraped_text)
print(f"{len(documents)}個の知識チャンクが作成されました。")

# 4. テキストをベクトル化し、FAISSデータベースを構築
print("知識のベクトル化とデータベースの構築を開始します...")
print("（初回はモデルのダウンロードに時間がかかる場合があります）")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

vectorstore = FAISS.from_texts(documents, embeddings)
print("データベースの構築が完了しました。")

# 5. 完成した知識ベースをファイルに保存
KNOWLEDGE_BASE_FILE = "shin_knowledge.faiss"
vectorstore.save_local(KNOWLEDGE_BASE_FILE)
print(f"\n知識ベースが '{KNOWLEDGE_BASE_FILE}' として保存されました！")
print("これ以降は、メインのAIプログラムを実行してください。")
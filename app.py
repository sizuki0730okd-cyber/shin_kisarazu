# (必要なライブラリやHTMLテンプレートは前回と同じなので省略します)
# -----------------------------
# 必要ライブラリ
# -----------------------------
# pip install flask pyqrcode pypng Pillow google-generativeai requests beautifulsoup4 langchain langchain-community sentence-transformers faiss-cpu google-api-python-client markdown2
import tkinter as tk
from tkinter import font as tkfont
import threading
import pyqrcode
from PIL import Image, ImageTk
from flask import Flask, Response, render_template_string, request, jsonify
import socket
import queue
import os
import time
import json
import google.generativeai as genai
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
import markdown2
import random

# -----------------------------
# グローバル変数
# -----------------------------
try:
    # ★★★ 環境変数からキーを読み込むように変更 ★★★
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY")
    SEARCH_ENGINE_ID = os.environ.get("SEARCH_ENGINE_ID")
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    google_search_service = build("customsearch", "v1", developerKey=SEARCH_API_KEY)
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    knowledge_base = None
    API_CONFIGURED = True
except Exception as e:
    print(f"APIキーまたはモデルの初期化でエラー: {e}")
    API_CONFIGURED = False
    model = None

conversation_history = []
MAX_HISTORY = 5


# -----------------------------
# Flaskサーバー（簡易Web版）
# -----------------------------
# (前略)
app = Flask(__name__)

# ★★★ UI/UXの最終完成形（v4） ★★★
html_template = """
<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>Shin君 | 木更津専門AI</title>
<script src="https://cdn.jsdelivr.net/npm/markdown-it@14.1.0/dist/markdown-it.min.js"></script>
<style>
    /* (スタイル部分は変更なしのため省略) */
    html, body { height: 100%; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Hiragino Kaku Gothic ProN", "Meiryo", sans-serif; background-color: #E5DDD5; } body { display: flex; flex-direction: column; } #chat-container { display: flex; flex-direction: column; flex-grow: 1; max-width: 600px; width: 100%; margin: 0 auto; box-shadow: 0 0 10px rgba(0,0,0,0.1); background-color: #E5DDD5; } #chat { flex-grow: 1; overflow-y: auto; padding: 20px 10px; } .bubble-container { display: flex; margin-bottom: 12px; max-width: 80%; } .bubble { padding: 8px 14px; border-radius: 18px; line-height: 1.5; box-shadow: 0 1px 1px rgba(0,0,0,0.1); position: relative; word-wrap: break-word; } .shin-container { justify-content: flex-start; margin-right: auto; } .shin .bubble { background-color: #FFFFFF; color: #333; } .shin .bubble::before { content: ''; position: absolute; top: 10px; left: -8px; border-top: 10px solid transparent; border-right: 12px solid #FFFFFF; border-bottom: 10px solid transparent; } .user-container { justify-content: flex-end; margin-left: auto; } .user .bubble { background-color: #8DE041; color: #000; } .user .bubble::after { content: ''; position: absolute; top: 10px; right: -8px; border-top: 10px solid transparent; border-left: 12px solid #8DE041; border-bottom: 10px solid transparent; } .name-feedback-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; padding: 0 5px; } .name { font-size: 0.8em; color: #555; } .feedback-buttons { display: flex; gap: 5px; } .feedback-btn { cursor: pointer; font-size: 14px; opacity: 0.5; transition: all 0.2s; } .feedback-btn:hover { opacity: 1; transform: scale(1.1); } .feedback-btn.selected { opacity: 1; } #form { display: flex; align-items: center; padding: 10px; background-color: #f0f0f0; border-top: 1px solid #dcdcdc; } #msg { flex-grow: 1; padding: 10px 15px; border: 1px solid #dcdcdc; border-radius: 20px; font-size: 16px; background-color: #fff; } #msg:focus { outline: none; border-color: #8DE041; } #send-btn { width: 40px; height: 40px; border: none; border-radius: 50%; background-color: #007BFF; color: white; margin-left: 8px; cursor: pointer; font-size: 20px; display: flex; justify-content: center; align-items: center; transition: background-color 0.2s; } #send-btn:hover { background-color: #0056b3; } .bubble p:last-child { margin-bottom: 0; } .bubble ul { padding-left: 20px; margin-top: 0; } .bubble strong { font-weight: bold; }
    @keyframes blink { 50% { opacity: 0; } } .blinking-cursor { display: inline-block; width: 8px; height: 1.2em; background-color: #333; animation: blink 1s step-end infinite; vertical-align: text-bottom; }
</style>
</head>
<body>
<div id="chat-container">
    <div id="chat"></div>
    <div id="form">
        <input type="text" id="msg" placeholder="メッセージを入力..." onkeydown="if(event.key==='Enter' && !event.shiftKey){ event.preventDefault(); sendMessage();}">
        <button id="send-btn" onclick="sendMessage()">&#x27A4;</button>
    </div>
</div>

<script>
    const md = window.markdownit();

    async function sendMessage() {
        const msgInput = document.getElementById("msg");
        const msg = msgInput.value.trim();
        if (!msg) return;

        const chat = document.getElementById("chat");
        // ★★★ ユーザーの吹き出しにクラス名を追加 ★★★
        chat.innerHTML += `<div class="bubble-container user-container"><div class="bubble">${escapeHTML(msg)}</div></div>`;
        msgInput.value = "";
        chat.scrollTop = chat.scrollHeight;

        const bubbleId = 'bubble-' + Date.now();
        const thinkingHTML = `
            <div class="bubble-container shin-container" id="${bubbleId}">
                <div class="bubble-content">
                    <div class="name-feedback-row"><div class="name">Shin</div></div>
                    <div class="bubble shin">
                        <span class="content"></span><span class="blinking-cursor"></span>
                    </div>
                </div>
            </div>`;
        chat.innerHTML += thinkingHTML;
        chat.scrollTop = chat.scrollHeight;
        
        const eventSource = new EventSource(`/stream?message=${encodeURIComponent(msg)}`);
        const contentSpan = document.querySelector(`#${bubbleId} .content`);
        const cursorSpan = document.querySelector(`#${bubbleId} .blinking-cursor`);
        
        let fullReply = ""; // 最終的な回答を保持する変数

        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            if (data.type === 'token') {
                fullReply += data.content;
                // ★★★ 意図的に一文字ずつ表示する演出 ★★★
                let i = 0;
                function typeChar() {
                    if (i < data.content.length) {
                        contentSpan.innerHTML += data.content.charAt(i);
                        i++;
                        chat.scrollTop = chat.scrollHeight;
                        setTimeout(typeChar, 5); // 5ミリ秒ごとに一文字表示
                    }
                }
                typeChar();

            } else if (data.type === 'end') {
                cursorSpan.remove();
                eventSource.close();
                
                document.querySelector(`#${bubbleId} .bubble`).innerHTML = md.render(fullReply);
                
                const feedbackDiv = document.createElement('div');
                feedbackDiv.className = 'feedback-buttons';
                feedbackDiv.innerHTML = `<span class="feedback-btn" onclick="sendFeedback('${bubbleId}', 'good')">👍</span> <span class="feedback-btn" onclick="sendFeedback('${bubbleId}', 'bad')">👎</span>`;
                document.querySelector(`#${bubbleId} .name-feedback-row`).appendChild(feedbackDiv);
            }
        };
        eventSource.onerror = function(err) { cursorSpan.remove(); contentSpan.innerHTML = "エラーが発生しました。"; eventSource.close(); };
    }

    // ★★★ 質問文の取得ロジックを修正 ★★★
    function sendFeedback(bubbleId, rating) {
        const bubbleElem = document.getElementById(bubbleId);
        const allUserBubbles = Array.from(document.querySelectorAll('.user-container'));
        const questionElem = allUserBubbles[allUserBubbles.length - 1]; // 最後のユーザー発言を取得
        const question = questionElem ? questionElem.querySelector('.bubble').textContent : 'N/A';
        const answer = bubbleElem.querySelector('.bubble').textContent;
        
        fetch("/feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, answer, rating }) });
        
        const buttons = bubbleElem.querySelectorAll('.feedback-btn');
        buttons.forEach(btn => btn.classList.remove('selected'));
        bubbleElem.querySelector(rating === 'good' ? '.feedback-btn:first-child' : '.feedback-btn:last-child').classList.add('selected');
    }

    function escapeHTML(str) { return str.replace(/[&<>"']/g, function(match) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[match]; }); }

    // ★★★ 挨拶メッセージのHTML構造を修正 ★★★
    window.onload = function() {
        const chat = document.getElementById("chat");
        const welcomeMessage = "こんにちは！ 僕は木更津市と木更津高校に詳しいAIの「Shin」だよ。**なんでも気軽に質問してね！**";
        const welcomeHTML = `
            <div class="bubble-container shin-container">
                <div class="bubble-content">
                    <div class="name-feedback-row"><div class="name">Shin</div></div>
                    <div class="bubble shin">${md.render(welcomeMessage)}</div>
                </div>
            </div>`;
        chat.innerHTML += welcomeHTML;
    };
</script>
</body>
</html>
"""



# (以降のPythonコードは、前回の回答から一切変更ありません)
# ... (app = Flask(__name__) より前の部分)
# app = Flask(__name__)
# html_template = """...""" # 上記の新しいテンプレートに置き換え
# (以降の @app.route("/") から __main__ まで、全て変更なし)

def classify_user_intent(user_message):
    try:
        prompt = f"""ユーザーの発言を分析し、その意図を「Question」（情報を求める質問）か「Chit-chat」（挨拶、感謝、相槌などの雑談）のどちらかに分類してください。\n出力は「Question」か「Chit-chat」の単語だけにしてください。\n---\n[例]\nユーザー: こんにちは\n分類: Chit-chat\nユーザー: 木更津市の名産品は？\n分類: Question\nユーザー: すごいね！ありがとう！\n分類: Chit-chat\n---\nユーザー: {user_message}\n分類:"""
        response = model.generate_content(prompt)
        intent = response.text.strip()
        print(f"意図分類の結果: {intent}")
        return "Question" if "Question" in intent else "Chit-chat"
    except Exception as e:
        print(f"意図分類中にエラー: {e}"); return "Question"
def generate_chitchat_response(user_message):
    if "ありがとう" in user_message or "すごい" in user_message: return random.choice(["どういたしまして！お役に立てて嬉しいよ。", "えへへ、もっと僕を頼ってくれていいんだよ！", "またいつでも聞いてね！"])
    elif "こんにちは" in user_message or "やあ" in user_message: return random.choice(["こんにちは！今日は何か面白いことあった？", "やあ！木更津のことなら何でも聞いてね。"])
    else: return "うんうん、そうだね！"
def generate_search_queries(question):
    try:
        prompt = f"ユーザーからの以下の質問に答えるために最も効果的だと思われるGoogle検索キーワードを3つ、箇条書きで生成してください。\n# 質問: {question}\n# 検索キーワード:"
        response = model.generate_content(prompt)
        return [q.strip().lstrip('- ') for q in response.text.strip().split('\n')]
    except Exception as e:
        print(f"検索キーワードの生成に失敗: {e}"); return [question]
def google_search(query):
    try:
        res = google_search_service.cse().list(q=query, cx=SEARCH_ENGINE_ID, num=3).execute()
        return [item['link'] for item in res.get('items', [])]
    except Exception as e:
        print(f"Google検索に失敗: {e}"); return []
def scrape_website_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status(); response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "header", "footer", "nav", "aside"]): tag.decompose()
        return ' '.join(t.strip() for t in soup.body.find_all(string=True) if t.strip())[:2000]
    except Exception as e:
        print(f"スクレイピングに失敗 ({url}): {e}"); return ""

@app.route("/")
def index():
    return render_template_string(html_template)

@app.route("/stream")
def stream():
    user_msg = request.args.get('message', '')
    if not user_msg: return Response("data: {\"type\": \"token\", \"content\": \"メッセージが空です。\"}\n\n", mimetype='text/event-stream')
    def generate_response():
        global conversation_history
        try:
            intent = classify_user_intent(user_msg)
            if intent == "Chit-chat":
                reply = generate_chitchat_response(user_msg)
                yield f"data: {json.dumps({'type': 'token', 'content': reply})}\n\n"
            else:
                similar_docs = knowledge_base.similarity_search(user_msg, k=4)
                context = "\n\n".join([doc.page_content for doc in similar_docs])
                
                evaluation_prompt = f"""# 命令書\nあなたはユーザーの質問に対し、提供された「参考情報」だけで答えられるか判断するAIです。\n- もし参考情報だけで自信を持って答えられる場合は、その答えを生成してください。\n- もし参考情報が不十分で、ウェブ検索が必要だと判断した場合は、他の言葉は一切出力せず、ただ一言 **SEARCH_REQUIRED** とだけ出力してください。\n# 参考情報\n{context}\n\n---\n# 質問\n{user_msg}\n\n# あなたの応答 (回答本文 または SEARCH_REQUIRED)"""
                initial_response = model.generate_content(evaluation_prompt).text.strip()

                if "SEARCH_REQUIRED" in initial_response:
                    yield f"data: {json.dumps({'type': 'token', 'content': 'ふむふむ、少し詳しい情報が必要そうですね。ウェブで調べてみます！'})}\n\n"
                    time.sleep(1) # メッセージを見せるための時間
                    search_queries = generate_search_queries(user_msg)
                    web_knowledge = ""
                    unique_links = set()
                    for query in search_queries:
                        for link in google_search(query):
                            if link not in unique_links:
                                unique_links.add(link)
                                web_knowledge += f"## ウェブ検索結果\n{scrape_website_text(link)}\n\n"
                    prompt = f"""# 命令書\nあなたは「Shin」という木更津市の専門家AIです。\n以下の「基本知識」と「ウェブからの最新情報」を統合し、質問に答えてください。\n# ルール\n- 両方の情報を参考にすること。\n- 親しみやすい口調で簡潔に答えること。\n- 答えがない場合は「ウェブでも調べてみましたが、正確な情報は見つかりませんでした。」と答えること。\n# 基本知識\n{context}\n\n# ウェブからの最新情報\n{web_knowledge if web_knowledge else "有益な情報は見つかりませんでした。"}\n\n# 会話履歴\n{conversation_history}\n\n---\n# 質問\n{user_msg}\n# 回答"""
                    stream_gen = model.generate_content(prompt, stream=True)
                else:
                    yield f"data: {json.dumps({'type': 'token', 'content': initial_response})}\n\n"
                    stream_gen = None # ストリーミングは不要
                    full_reply = initial_response

                if stream_gen:
                    full_reply = ""
                    for chunk in stream_gen:
                        if not hasattr(chunk, 'text'): continue
                        full_reply += chunk.text
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.text})}\n\n"
                
                conversation_history.append({"role": "user", "parts": [user_msg]})
                conversation_history.append({"role": "model", "parts": [full_reply]})
                if len(conversation_history) > MAX_HISTORY * 2:
                    conversation_history = conversation_history[-MAX_HISTORY*2:]
        except Exception as e:
            print(f"ストリーム生成中にエラー: {e}")
            yield f"data: {json.dumps({'type': 'token', 'content': f'申し訳ありません、エラーが発生しました: {e}'})}\n\n"
        yield f"data: {json.dumps({'type': 'end'})}\n\n"
    return Response(generate_response(), mimetype='text/event-stream')

@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.json
    with open("feedback.log", "a", encoding="utf-8") as f: f.write(json.dumps(data, ensure_ascii=False) + "\n")
    return jsonify({"status": "ok"})
def run_flask():
    from werkzeug.serving import make_server
    class ServerThread(threading.Thread):
        def __init__(self, app): threading.Thread.__init__(self); self.server = make_server('0.0.0.0', 5000, app, threaded=True); self.ctx = app.app_context(); self.ctx.push()
        def run(self): self.server.serve_forever()
    ServerThread(app).start()
def get_local_ip():
    try: s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('10.255.255.255', 1)); ip = s.getsockname()[0]; s.close(); return ip;
    except Exception: return '127.0.0.1'
def setup_and_run(status_queue):
    global knowledge_base
    try:
        KNOWLEDGE_BASE_FILE = "shin_knowledge.faiss"
        status_queue.put(f"知識ベース '{KNOWLEDGE_BASE_FILE}' を読み込み中...")
        if not os.path.exists(KNOWLEDGE_BASE_FILE): status_queue.put(f"エラー: 知識ベースファイルが見つかりません。\n先に`build_knowledge_base.py`を実行してください。"); return
        knowledge_base = FAISS.load_local(KNOWLEDGE_BASE_FILE, embeddings, allow_dangerous_deserialization=True)
        status_queue.put("知識ベースの準備完了。")
        if not API_CONFIGURED: status_queue.put("エラー: APIキーが設定されていません。"); return
        status_queue.put("Flaskサーバーを起動中...")
        run_flask()
        status_queue.put("完了")
    except Exception as e: status_queue.put(f"致命的なエラーが発生しました:\n{type(e).__name__}: {e}")
def create_main_window():
    root = tk.Tk(); root.title("Shin君 AIサーバー"); root.geometry("400x500")
    status_font = tkfont.Font(family="Helvetica", size=12)
    status_label = tk.Label(root, text="準備中...", font=status_font, justify=tk.CENTER, wraplength=380); status_label.pack(pady=20, expand=True)
    ui_queue = queue.Queue()
    def update_ui():
        try:
            message = ui_queue.get_nowait()
            if message == "完了":
                [widget.destroy() for widget in root.winfo_children()]
                tk.Label(root, text="サーバーを起動しました", font=("Helvetica",16, "bold")).pack(pady=10)
                local_ip = get_local_ip(); local_url = f"http://{local_ip}:5000"
                tk.Label(root, text="▼同じWi-Fi内のスマホでアクセス▼", font=("Helvetica",12)).pack(pady=(20, 5))
                tk.Label(root, text=f"URL: {local_url}", font=("Helvetica",10)).pack()
                qr_path = "shin_chat_qr.png"; qr = pyqrcode.create(local_url); qr.png(qr_path, scale=5); img = Image.open(qr_path); img_tk = ImageTk.PhotoImage(img)
                label_qr = tk.Label(root, image=img_tk); label_qr.image = img_tk; label_qr.pack(pady=10)
                tk.Label(root, text="▼外部の端末からアクセスする場合▼", font=("Helvetica", 12)).pack(pady=(20, 5))
                ngrok_text = "1. ngrok をインストール\n2. ターミナルで ngrok http 5000 を実行\n3. 表示されたURLにアクセス"
                tk.Label(root, text=ngrok_text, font=("Helvetica",10), justify=tk.LEFT).pack()
            else: status_label.config(text=message)
        except queue.Empty: pass
        root.after(100, update_ui)
    threading.Thread(target=setup_and_run, args=(ui_queue,), daemon=True).start()
    root.after(100, update_ui)
    root.mainloop()

if __name__ == "__main__":
    create_main_window()
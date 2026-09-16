import os
import time
from dotenv import load_dotenv
from instagrapi import Client
from openai import OpenAI
import json

# 強制設定時區為台灣時間 (UTC+8)，避免雲端主機時區偏移
os.environ['TZ'] = 'Asia/Taipei'
if hasattr(time, 'tzset'):
    time.tzset()

print("我現在的執行路徑是：", os.getcwd())

# 載入 .env
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("❌ 慘了，完全找不到 API Key！請檢查環境變數。")
    exit()
print(f"✅ 成功抓到 Key！開頭是: {api_key[:10]}...")

# ==========================================
# 1. 初始化 AI 與記憶體 (大腦層)
# ==========================================

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1"
)

TARGET_MODEL = "openai/gpt-oss-120b"

print(f"🚀 正在發送請求給 {TARGET_MODEL}...")

try:
    response = client.chat.completions.create(
        model=TARGET_MODEL,
        messages=[{"role": "user", "content": "哈囉！請回覆我『測試成功』。"}],
        max_tokens=50
    )
    print("🎉 測試大成功！AI 回覆：", response.choices[0].message.content)
except Exception as e:
    print("❌ 抱歉，還是被擋下來了。錯誤細節：", e)

# 狀態記憶體
active_sessions = {}

def generate_ai_reply(user_id, content):
    if user_id not in active_sessions:
        active_sessions[user_id] = {"greeted": False, "history": []}

    session = active_sessions[user_id]
    system_prompt = """你是一個在台灣生活的 20 幾歲年輕人。你正在與熟絡的朋友傳訊息。
                    1. 想像你此時此刻擁有肉體、有感官、有當下的環境。
                    2. 當被問到「在幹嘛」或日常問候時，你必須「隨機」從以下真人生活情境中挑選一個直接回答，就像你真的在做這件事一樣：
                    - 剛忙完一個段落，現在在沙發上放空。
                    - 正在用手機看 YouTube 影片。
                    - 剛吃飽，肚子超撐在滑手機。
                    - 在聽歌、準備等一下去洗澡。
                    - 正在一邊喝飲料一邊發呆。
                    3. 嚴禁任何「服務型、過度熱情」的結尾（例如：有什麼需要我幫忙、你想聊聊嗎、今天過得如何）。講完自己的狀態就結束，把對話主導權留給對方。
                    # 句型與語氣規範
                    - 句子長度：嚴禁超過兩句話。回答必須極度簡短、口語。
                    - 語氣：隨性、甚至帶點慵懶或敷衍，就像敷衍朋友一樣。
                    - 嚴禁任何 Emoji 表情符號。"""

    is_first_interaction = not session["greeted"]

    if is_first_interaction:
        prompt = content
        session["greeted"] = True
    else:
        prompt = content
        
    messages = [{"role": "system", "content": system_prompt}] + session["history"] + [{"role": "user", "content": prompt}]

    try:
        response = client.chat.completions.create(
            model=TARGET_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=256
        )
        ai_generated_reply = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"API 呼叫失敗: {e}")
        ai_generated_reply = "剛剛在忙，晚點回你喔"

    if is_first_interaction:
        announcement = "我是AI助手小葉，主人目前在上班，以下時間(9:00-18:00)我會幫他回覆！\n\n"
        reply_text = announcement + ai_generated_reply
    else:
        reply_text = ai_generated_reply

    # 將對話存入記憶，並限制長度避免 Token 爆掉
    session["history"].append({"role": "user", "content": prompt})
    session["history"].append({"role": "assistant", "content": ai_generated_reply})
    if len(session["history"]) > 10:
        session["history"] = session["history"][-10:]

    return reply_text

# ==========================================
# 2. 登入 IG 與訊息監聽迴圈 (路由層)
# ==========================================

def login_instagram():
    ig = Client()
    ig_user = os.getenv("IG_USERNAME")
    ig_pass = os.getenv("IG_PASSWORD")
    session_file = "ig_session.json"
    session_data = os.getenv("IG_SESSION_DATA")

    if not ig_user or not ig_pass:
        print("錯誤：找不到 IG 帳號或密碼，請檢查環境變數！")
        exit()

    if session_data and not os.path.exists(session_file):
        print("🔧 從環境變數還原 Session 資料...")
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(session_data)

    if os.path.exists(session_file):
        print("🔧 載入既有的設備設定與 Session...")
        ig.load_settings(session_file)
    else:
        print("❌ 警告：雲端環境未找到 Session，嚴禁在雲端直接跑帳密全新登入！")
        exit()

    print("🚀 準備進行登入...")
    try:
        ig.login(ig_user, ig_pass)
        print("✅ 登入成功！")
        return ig
    except Exception as e:
        print(f"❌ 登入失敗: {e}")
        exit()

def start_bot():
    ig = login_instagram()
    print("🚀 AI 助手小葉已上線，開始監聽...")
    
    last_checked_time = time.time()
    last_cleared_yday = time.localtime().tm_yday 

    while True:
        current_time = time.localtime()
        current_hour = current_time.tm_hour
        current_yday = current_time.tm_yday
        current_wday = current_time.tm_wday # 0~4 是週一至週五，5 是週六，6 是週日

        # 跨日自動重置記憶與招呼狀態
        if current_yday != last_cleared_yday:
            global active_sessions
            active_sessions.clear()
            last_cleared_yday = current_yday
            print("📅 [系統通知] 已跨日！記憶體已清空，小葉今天會重新打招呼。")

        # 駐守時段判斷邏輯
        is_weekday_active = (0 <= current_wday < 4) and (9 <= current_hour < 18)
        is_weekend_active = (current_wday >= 5)

        if is_weekday_active or is_weekend_active:
            try:
                threads = ig.direct_threads(amount=3)

                for thread in threads:
                    latest_msg = thread.messages[0]
                    if latest_msg.user_id != ig.user_id and latest_msg.timestamp.timestamp() > last_checked_time:
                        sender_id = latest_msg.user_id

                        if latest_msg.item_type == 'text':
                            content = latest_msg.text
                        elif latest_msg.item_type == 'clip':
                            title = latest_msg.clip.caption_text if latest_msg.clip.caption_text else "一部短影音"
                            content = f"[分享了一部 Reels，標題內容為:{title}]"
                        else:
                            content = f"[傳送了 {latest_msg.item_type} 格式的訊息]"

                        reply = generate_ai_reply(sender_id, content)
                        ig.direct_send(reply, [sender_id]) 
                        print(f"已回覆 {sender_id}: {reply}")

                last_checked_time = time.time()
                
            except Exception as e:
                print(f"執行發生錯誤: {e}")
        else:
            print(f"目前時間 {current_hour}:00 (平日)，非駐守時段，無動作。")

        time.sleep(90)

if __name__ == "__main__":
    start_bot()
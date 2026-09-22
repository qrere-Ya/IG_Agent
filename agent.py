import os
import time
from dotenv import load_dotenv
from instagrapi import Client
from openai import OpenAI
import json
import random

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
    # 靈活、自然的人設，避免死板清單
    system_prompt = """你是一個在台灣生活的 20 幾歲年輕男生，正在 IG 跟熟朋友聊天。
                        你的身份是替大葉代班回覆的「小葉」。
                        個性：隨和、幽默、微帶點幹話和慵懶感，講話很口語，不會打官腔。

                        原則：
                        1. 嚴禁條列式、嚴禁服務型結尾（不要說「有什麼需要幫忙」、「你想聊什麼」）。
                        2. 對方問什麼就順著聊，不要每次都跳針說自己在沙發放空或看YT。
                        3. 對方如果傳很多句或開玩笑（例如問你主人是不是大葉、傳梗圖），就自然吐槽或接梗。
                        4. 長度短一點，1~2 句話結束，嚴禁使用任何 Emoji。"""

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
            temperature=0.75,
            max_tokens=200
        )
        ai_generated_reply = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"API 呼叫失敗: {e}")
        ai_generated_reply = "剛剛在忙，晚點回你喔"

    if is_first_interaction:
        # 擴充隨機稱呼清單
        owner_aliases = [
            "社畜",
            "白癡",
            "大葉",
            "牛馬",
            "打工仔",
            "薪水小偷",
            "那個廢物",
            "那隻狗",
            "那位仁兄",
            "低薪勞工"
        ]
        owner_alias = random.choice(owner_aliases)
        announcement = f"我是AI助手小葉，{owner_alias}目前在上班，以下時間(9:00-18:00)我會幫他回覆！\n\n"
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
            print("📅 [系統通知] 已跨日！記憶體已清空。")

        # 駐守時段判斷邏輯
        is_mon_to_thu_work_hours = (0 <= current_wday <= 3) and (9 <= current_hour < 18)

        if is_mon_to_thu_work_hours:
            try:
                threads = ig.direct_threads(amount=5)

                for thread in threads:
                    new_msgs = [
                        m for m in thread.messages 
                        if m.user_id != ig.user_id and m.timestamp.timestamp() > last_checked_time
                    ]

                    if not new_msgs:
                        continue

                    sender_id = new_msgs[0].user_id
                    new_msgs.sort(key=lambda m: m.timestamp.timestamp())
                    
                    collected_texts = []
                    for m in new_msgs:
                        if m.item_type == 'text':
                            collected_texts.append(m.text)
                        elif m.item_type == 'clip':
                            caption = m.clip.caption_text if m.clip.caption_text else "短影音"
                            collected_texts.append(f"[傳送了Reels: {caption}]")
                        elif m.item_type in ['photo', 'animated_media', 'raven_media']:
                            collected_texts.append("[傳送了一張圖片或梗圖]")
                        else:
                            collected_texts.append(f"[{m.item_type}]")

                    combined_content = "\n".join(collected_texts)
                    print(f"收到來自 {sender_id} 的連續訊息:\n{combined_content}")

                    reply = generate_ai_reply(sender_id, combined_content)
                    ig.direct_send(reply, [sender_id]) 
                    print(f"已回覆 {sender_id}: {reply}")

                last_checked_time = time.time()
                
            except Exception as e:
                print(f"執行發生錯誤: {e}")
        else:
            print(f"目前時間 {current_hour}:00 (星期 {current_wday+1})，非駐守時段，放假中。")

        # 暫停 90 秒
        time.sleep(90)

if __name__ == "__main__":
    start_bot()
import datetime
import os
from flask import Flask, request
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    JoinEvent,
    LeaveEvent,
)

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

user_chat_counts = {}

@app.route("/", methods=['GET'])
def home():
    return "Line Bot is running!", 200

def get_user_name(group_id, room_id, user_id):
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            if group_id:
                profile = line_bot_api.get_group_member_profile(group_id, user_id)
            elif room_id:
                profile = line_bot_api.get_room_member_profile(room_id, user_id)
            else:
                return "사용자"
            return profile.display_name
    except Exception as e:
        print(f"프로필 조회 에러: {e}")
        return "사용자"

def sync_group_members(group_id, room_id, user_data):
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            member_ids = []
            if group_id:
                response = line_bot_api.get_group_member_user_ids(group_id)
                member_ids = response.member_ids
            elif room_id:
                response = line_bot_api.get_room_member_user_ids(room_id)
                member_ids = response.member_ids
            
            for uid in member_ids:
                if uid not in user_data:
                    name = get_user_name(group_id, room_id, uid)
                    user_data[uid] = {'display_name': name, 'count': 0, 'total_under_count': 0}
    except Exception as e:
        print(f"⚠️ 멤버 목록 조회 차단됨 (라인 API 정책): {e}")

def check_and_reset(chat_key, group_id, room_id):
    today = datetime.date.today().strftime('%Y-%m-%d')
    if chat_key not in user_chat_counts:
        user_chat_counts[chat_key] = {'last_reset': today, 'users': {}}
    
    room_data = user_chat_counts[chat_key]
    sync_group_members(group_id, room_id, room_data['users'])

    if room_data['last_reset'] != today:
        yesterday_users = room_data['users']
        for user in yesterday_users.values():
            if user['count'] < 30:
                user['total_under_count'] = user.get('total_under_count', 0) + 1
        
        under_active = [u for u in yesterday_users.values() if u['count'] < 30]
        if under_active:
            under_active.sort(key=lambda x: x['count'])
            warning_msg = "📢 [어제 활동 마감 알림]\n30마디를 채우지 못한 멤버가 있습니다.\n"
            for user in under_active:
                warning_msg += f"\n• {user['display_name']} ({user['count']}마디) - 총 미달 {user['total_under_count']}회 ⚠️"
            try:
                with ApiClient(configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    line_bot_api.push_message(chat_key, PushMessageRequest(to=chat_key, messages=[TextMessage(text=warning_msg)]))
            except Exception:
                pass
        
        new_users_data = {}
        for user_id, user in yesterday_users.items():
            new_users_data[user_id] = {'display_name': user['display_name'], 'count': 0, 'total_under_count': user['total_under_count']}
        room_data['users'] = new_users_data
        room_data['last_reset'] = today

@app.route("/callback", methods=['POST', 'GET'])
def callback():
    if request.method == 'GET':
        return 'OK', 200

    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    
    if not body or '"events":[]' in body:
        return 'OK', 200
    
    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"웹훅 에러 발생: {e}")
        
    return 'OK', 200

@handler.add(JoinEvent)
def handle_join(event):
    return 'OK'

@handler.add(LeaveEvent)
def handle_leave(event):
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    group_id = getattr(event.source, 'group_id', None)
    room_id = getattr(event.source, 'room_id', None)
    chat_key = group_id or room_id or event.source.user_id
    
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    check_and_reset(chat_key, group_id, room_id)
    user_data = user_chat_counts[chat_key]['users']

    sync_group_members(group_id, room_id, user_data)

    if user_id not in user_data:
        user_name = get_user_name(group_id, room_id, user_id)
        user_data[user_id] = {'display_name': user_name, 'count': 0, 'total_under_count': 0}

    reply_msg = ""

    if user_text in ["/마디", "/마디수"]:
        count = user_data[user_id]['count']
        name = user_data[user_id]['display_name']
        reply_msg = f"📊 {name}님의 현재 마디 수: {count}마디"
    elif user_text == "/순위":
        sorted_users = sorted(user_data.values(), key=lambda x: x['count'], reverse=True)
        reply_msg = "🏆 오늘의 마디 수 순위 🏆\n"
        for idx, user in enumerate(sorted_users, 1):
            reply_msg += f"\n{idx}위. {user['display_name']} ({user['count']}개)"
    elif user_text in ["/미달", "/경고", "/30마디"]:
        under_active = [u for u in user_data.values() if u['count'] < 30]
        if not under_active:
            reply_msg = "🎉 모든 멤버가 30마디 이상 작성했습니다!"
        else:
            under_active.sort(key=lambda x: x['count'])
            reply_msg = "⚠️ 30마디 미만 활동자 목록 ⚠️\n"
            for user in under_active:
                reply_msg += f"\n• {user['display_name']}: {user['count']}마디 (총 미달 {user.get('total_under_count', 0)}회)"
    elif user_text in ["/도움말", "/명령어"]:
        reply_msg = (
            "🤖 [마디 봇 명령어 안내]\n\n"
            "• /마디: 내 마디 수 확인\n"
            "• /순위: 전체 마디 순위 확인\n"
            "• /미달: 30마디 미만 멤버 확인\n"
            "• /초기화: 강제 초기화"
        )
    elif user_text == "/초기화":
        user_chat_counts[chat_key]['users'] = {}
        reply_msg = "🔄 현재 방의 데이터가 초기화되었습니다."
    else:
        user_data[user_id]['count'] += 1
        return

    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply_msg)]))
    except Exception:
        pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


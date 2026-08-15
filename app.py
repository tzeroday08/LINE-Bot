import os
import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, JoinEvent, LeaveEvent

app = Flask(__name__)

# 환경 변수 로드
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 데이터 구조: 
# { 
#     'chat_key': {
#         'last_reset': 'YYYY-MM-DD', 
#         'users': {
#             'user_id': {'display_name': str, 'count': int, 'total_under_count': int}
#         }
#     }
# }
user_chat_counts = {}

def get_user_name(group_id, user_id):
    """그룹 멤버의 디스플레이 닉네임을 가져옵니다."""
    try:
        profile = line_bot_api.get_group_member_profile(group_id, user_id)
        return profile.display_name
    except Exception:
        return "사용자"

def check_and_reset(chat_key):
    """날짜 변경 시 마디 수를 초기화하고, 전날 미달자에게 총 미달 횟수를 누적 및 경고합니다."""
    today = datetime.date.today().strftime('%Y-%m-%d')
    
    if chat_key not in user_chat_counts:
        user_chat_counts[chat_key] = {'last_reset': today, 'users': {}}
        return
    
    room_data = user_chat_counts[chat_key]
    
    if room_data['last_reset'] != today:
        yesterday_users = room_data['users']
        
        # 전날 미달자(30마디 미만) 총 미달 횟수 누적
        for user in yesterday_users.values():
            if user['count'] < 30:
                user['total_under_count'] = user.get('total_under_count', 0) + 1
        
        # 미달자 목록 추출
        under_active = [u for u in yesterday_users.values() if u['count'] < 30]
        
        if under_active:
            under_active.sort(key=lambda x: x['count'])
            warning_msg = "📢 [어제 활동 마감 알림]\n30마디를 채우지 못한 멤버가 있습니다.\n"
            for user in under_active:
                warning_msg += f"\n• {user['display_name']} ({user['count']}마디) - 총 미달 {user['total_under_count']}회 ⚠️"
            
            try:
                line_bot_api.push_message(chat_key, TextSendMessage(text=warning_msg))
            except Exception:
                pass
        
        # 오늘의 데이터로 갱신 (누적 미달 횟수는 유지, count는 0으로 초기화)
        new_users_data = {}
        for user_id, user in yesterday_users.items():
            new_users_data[user_id] = {
                'display_name': user['display_name'],
                'count': 0,
                'total_under_count': user['total_under_count']
            }
            
        room_data['users'] = new_users_data
        room_data['last_reset'] = today

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 1. 봇 자신이 그룹에 초대되었을 때 (튕김 방지 및 환영 인사)
@handler.add(JoinEvent)
def handle_join(event):
    try:
        welcome_msg = (
            "안녕하세요! 마디 봇입니다. 💬\n"
            "매일 대화량을 측정하고 30마디 미달 시 알려드려요!\n"
            "사용 가능한 명령어는 /도움말 을 입력해주세요."
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome_msg))
    except Exception:
        pass
    return 'OK'

# 2. 다른 사용자가 그룹에서 나갈 때 (#ㄴㄱ 자동 감지)
@handler.add(LeaveEvent)
def handle_leave(event):
    try:
        chat_key = getattr(event.source, 'group_id', None) or getattr(event.source, 'room_id', None)
        if chat_key:
            line_bot_api.push_message(chat_key, TextSendMessage(text="#ㄴㄱ (멤버가 퇴장하셨습니다 😢)"))
    except Exception:
        pass
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    group_id = getattr(event.source, 'group_id', None)
    room_id = getattr(event.source, 'room_id', None)
    chat_key = group_id or room_id or event.source.user_id
    
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    # 날짜 변경 체크 및 자동 초기화
    check_and_reset(chat_key)
    
    user_data = user_chat_counts[chat_key]['users']

    # 신규 사용자 등록
    if user_id not in user_data:
        user_name = get_user_name(group_id, user_id) if group_id else "사용자"
        user_data[user_id] = {
            'display_name': user_name, 
            'count': 0, 
            'total_under_count': 0
        }

    # 1. 내 마디 수 확인
    if user_text in ["/마디", "/마디수"]:
        count = user_data[user_id]['count']
        name = user_data[user_id]['display_name']
        reply_msg = f"📊 {name}님의 현재 마디 수: {count}마디"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

    # 2. 순위 확인
    elif user_text == "/순위":
        sorted_users = sorted(user_data.values(), key=lambda x: x['count'], reverse=True)
        reply_msg = "🏆 오늘의 마디 수 순위 🏆\n"
        for idx, user in enumerate(sorted_users, 1):
            reply_msg += f"\n{idx}위. {user['display_name']} ({user['count']}개)"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

    # 3. 미달자 확인
    elif user_text in ["/미달", "/경고", "/30마디"]:
        under_active = [u for u in user_data.values() if u['count'] < 30]
        if not under_active:
            reply_msg = "🎉 모든 멤버가 30마디 이상 작성했습니다!"
        else:
            under_active.sort(key=lambda x: x['count'])
            reply_msg = "⚠️ 30마디 미만 활동자 목록 ⚠️\n"
            for user in under_active:
                reply_msg += f"\n• {user['display_name']}: {user['count']}마디 (총 미달 {user.get('total_under_count', 0)}회)"
            reply_msg += "\n\n소통에 더 참여해 주세요! 💬"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

    # 4. 도움말
    elif user_text in ["/도움말", "/명령어"]:
        reply_msg = (
            "🤖 [마디 봇 명령어 안내]\n\n"
            "• /마디: 내 마디 수 확인\n"
            "• /순위: 전체 마디 순위 확인\n"
            "• /미달: 30마디 미만 멤버 확인\n"
            "• /초기화: 강제 초기화\n"
            "• (멤버 퇴장 시 봇이 #ㄴㄱ 자동 알림 전송)\n"
            "• (매일 자정 이후 첫 메시지 시 자동 리셋 및 미달 경고)"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

    # 5. 수동 초기화
    elif user_text == "/초기화":
        user_chat_counts[chat_key]['users'] = {}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🔄 현재 방의 데이터가 초기화되었습니다."))

    # 6. 일반 메시지 마디 증가
    else:
        user_data[user_id]['count'] += 1

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

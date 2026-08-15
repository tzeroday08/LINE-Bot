import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, JoinEvent

app = Flask(__name__)

# Render 환경변수에서 Key 가져오기
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 데이터 저장 구조
# user_chat_counts = { group_id: { user_id: { 'display_name': str, 'count': int } } }
user_chat_counts = {}

# 유저 이름(프로필) 가져오기 유틸리티 함수
def get_user_name(group_id, user_id):
    try:
        profile = line_bot_api.get_group_member_profile(group_id, user_id)
        return profile.display_name
    except Exception:
        return "알 수 없는 사용자"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# 봇이 그룹에 참여할 때 자동 수락 처리
@handler.add(JoinEvent)
def handle_join(event):
    print(f"Joined group: {event.source.group_id}")

# 메시지 수신 이벤트 핸들러
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # 그룹 방이 아닌 1:1 대화인 경우 source.group_id 대신 source.user_id 사용
    source_id = getattr(event.source, 'group_id', None) or event.source.user_id
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    # 그룹 데이터 초기화
    if source_id not in user_chat_counts:
        user_chat_counts[source_id] = {}

    # 유저 데이터 초기화 및 이름 업데이트
    if user_id not in user_chat_counts[source_id]:
        user_name = get_user_name(source_id, user_id) if getattr(event.source, 'group_id', None) else "사용자"
        user_chat_counts[source_id][user_id] = {'display_name': user_name, 'count': 0}

    # 명령어 처리
    if user_text == "!마디수":
        count = user_chat_counts[source_id][user_id]['count']
        name = user_chat_counts[source_id][user_id]['display_name']
        reply_msg = f"📊 {name}님의 현재 마디 수: {count}마디"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

    elif user_text == "!순위":
        sorted_users = sorted(user_chat_counts[source_id].values(), key=lambda x: x['count'], reverse=True)
        if not sorted_users:
            reply_msg = "아직 기록된 대화가 없습니다."
        else:
            reply_msg = "🏆 **오늘의 마디 수 순위** 🏆\n"
            for idx, user in enumerate(sorted_users, 1):
                reply_msg += f"\n{idx}위. {user['display_name']}: {user['count']}마디"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

    elif user_text in ["!경고", "!미달", "!30마디"]:
        # 30마디 미만인 이용자 추출
        under_active_users = [
            user for user in user_chat_counts[source_id].values() 
            if user['count'] < 30
        ]
        
        if not under_active_users:
            reply_msg = "🎉 모든 멤버가 30마디 이상 작성했습니다!"
        else:
            # 마디 수가 적은 순서대로 정렬
            under_active_users.sort(key=lambda x: x['count'])
            reply_msg = "⚠️ **30마디 미만 활동자 목록** ⚠️\n"
            for user in under_active_users:
                reply_msg += f"\n• {user['display_name']}: {user['count']}마디"
            reply_msg += "\n\n소통에 더 참여해 주세요! 💬"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

    else:
        # 명령어 이외의 일반 대화 메시지일 때 카운트 +1
        user_chat_counts[source_id][user_id]['count'] += 1

if __name__ == "__main__":
    app.run()

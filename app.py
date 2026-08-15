import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, JoinEvent

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

user_chat_counts = {}

def get_user_name(group_id, user_id):
    try:
        profile = line_bot_api.get_group_member_profile(group_id, user_id)
        return profile.display_name
    except Exception:
        return "사용자"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 그룹에 들어올 때 튕기지 않도록 가입 이벤트 핸들러 추가
@handler.add(JoinEvent)
def handle_join(event):
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    source_id = getattr(event.source, 'group_id', None) or event.source.user_id
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    if source_id not in user_chat_counts:
        user_chat_counts[source_id] = {}

    if user_id not in user_chat_counts[source_id]:
        is_group = getattr(event.source, 'group_id', None) is not None
        user_name = get_user_name(source_id, user_id) if is_group else "사용자"
        user_chat_counts[source_id][user_id] = {'display_name': user_name, 'count': 0}

    if user_text in ["!마디", "!마디수"]:
        count = user_chat_counts[source_id][user_id]['count']
        name = user_chat_counts[source_id][user_id]['display_name']
        reply_msg = f"📊 {name}님의 현재 마디 수: {count}마디"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

    elif user_text == "!순위":
        sorted_users = sorted(user_chat_counts[source_id].values(), key=lambda x: x['count'], reverse=True)
        reply_msg = "🏆 오늘의 마디 수 순위 🏆\n"
        for idx, user in enumerate(sorted_users, 1):
            reply_msg += f"\n{idx}위. {user['display_name']} ({user['count']}개)"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

    elif user_text in ["!미달", "!경고", "!30마디"]:
        under_active = [u for u in user_chat_counts[source_id].values() if u['count'] < 30]
        if not under_active:
            reply_msg = "🎉 모든 멤버가 30마디 이상 작성했습니다!"
        else:
            under_active.sort(key=lambda x: x['count'])
            reply_msg = "⚠️ 30마디 미만 활동자 목록 ⚠️\n"
            for user in under_active:
                reply_msg += f"\n• {user['display_name']}: {user['count']}마디"
            reply_msg += "\n\n소통에 더 참여해 주세요! 💬"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

    else:
        user_chat_counts[source_id][user_id]['count'] += 1

if __name__ == "__main__":
    app.run()

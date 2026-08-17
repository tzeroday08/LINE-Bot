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
    ImageMessage,
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
    except Exception:
        return "사용자"

def check_and_reset(chat_key):
    today = datetime.date.today().strftime('%Y-%m-%d')
    if chat_key not in user_chat_counts:
        user_chat_counts[chat_key] = {'last_reset': today, 'users': {}}
        return
    
    room_data = user_chat_counts[chat_key]
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

    check_and_reset(chat_key)
    user_data = user_chat_counts[chat_key]['users']

    if user_id not in user_data:
        user_name = get_user_name(group_id, room_id, user_id)
        user_data[user_id] = {'display_name': user_name, 'count': 0, 'total_under_count': 0}

    messages_to_reply = []

    if user_text in ["/초대", "/ㅊㄷ"]:
        text_msg = (
            "🥡 초대 인증 멘션 \n\n"
            "☝🏻초대 인증을 원하실 경우\n"
            "인증자🍮를 \n"
            "멘션한 후\n"
            "“남(여)초 1명이요~” 라고 남겨주세요!\n\n"
            "✌🏻답변이 없을 경우\n"
            "나머지 운영진🍧🍦을 \n"
            "멘션해 주세요!\n"
            "@🍧이설⁰⁸ @🍦찰리⁰⁴\n"
            "@🍦하루⁰⁸\n"
            "＊┈┈┈┈＊┈┈┈┈＊┈┈┈┈\n"
            "🚫 멘션 복사 불가 🙅🏻‍♀️\n"
            "한 명씩 직접 입력하여 멘션해 주세요!\n"
            "답변한 운영진이 인증방으로 초대해드립니다.\n"
            "초대할 분을 인증방에 초대한 후 퇴장해 주세요・₊✧"
        )
        messages_to_reply = [TextMessage(text=text_msg)]
    elif user_text in ["/매너", "/ㅁㄴ"]:
        img_url = "https://raw.githubusercontent.com/tzeroday08/LINE-Bot/main/27.png"
        messages_to_reply = [
            ImageMessage(original_content_url=img_url, preview_image_url=img_url),
            ImageMessage(original_content_url=img_url, preview_image_url=img_url),
            ImageMessage(original_content_url=img_url, preview_image_url=img_url)
        ]
    elif user_text in ["/담타", "/ㄷㅌ"]:
        # 담배 사진 Raw 링크 적용
        img_url_damta = "https://raw.githubusercontent.com/tzeroday08/LINE-Bot/main/1786928966606.jpg"
        messages_to_reply = [ImageMessage(original_content_url=img_url_damta, preview_image_url=img_url_damta)]
    elif user_text in ["/성향", "/ㅅㅎ"]:
        messages_to_reply = [TextMessage(text="https://bdsm-test.info/")]
    elif user_text in ["/눈팅", "/ㄴㅌ"]:
        # 눈팅 밈 사진 Raw 링크 적용
        img_url_nunting = "https://raw.githubusercontent.com/tzeroday08/LINE-Bot/main/1786929074643.jpg"
        messages_to_reply = [ImageMessage(original_content_url=img_url_nunting, preview_image_url=img_url_nunting)]
    elif user_text in ["!라이어", "!라이어게임"]:
        text_msg = (
            "🎭 라이어 게임\n"
            "인원\n"
            "• 최소 6명\n"
            "• 최대 8~15명\n"
            "역할\n"
            "• 👥 시민:\n"
            "• 🎭 라이어: 1명\n\n"
            "진행 방법\n"
            "1. 방장이 참가자 모집\n"
            "2. 참가자에게 개별적으로 단어 전달\n"
            "3. 시민들은 모두 같은 단어를 받고, 라이어만 다른 단어를 받음\n"
            "4. 한 명씩 돌아가며 단어를 직접 말하지 않고 힌트를 줌\n"
            "5. 전원 발언 후 투표\n"
            "6. 가장 많은 표를 받은 사람 공개\n"
            "7. 라이어가 잡혔다면 마지막으로 원래 단어 맞히기\n"
            "8. 맞히면 라이어 승 / 못 맞히면 시민 승"
        )
        messages_to_reply = [TextMessage(text=text_msg)]
    elif user_text in ["!눈겜", "!눈치게임"]:
        text_msg = (
            "👀 NUNCHI GAME\n\n"
            "참가자 모집합니다 🙋\n"
            "참가할 사람은 `참여` 적어주세요!\n\n"
            "📌 RULE\n"
            "• 1부터 차례대로 숫자를 말해주세요.\n"
            "• 순서는 정해져 있지 않습니다.\n"
            "• 같은 숫자를 동시에 말하면 두 명 모두 탈락!\n"
            "• 숫자를 건너뛰거나 잘못 말하면 탈락!\n"
            "• 마지막까지 살아남은 사람이 우승 🏆"
        )
        messages_to_reply = [TextMessage(text=text_msg)]
    elif user_text in ["!3초", "!3초게임"]:
        text_msg = (
            "⚡ 3초 GAME\n\n"
            "지목된 사람은 질문을 듣자마자\n"
            "3초 안에 대답해주세요!\n\n"
            "📌 RULE\n"
            "• 제한시간 3초\n"
            "• 대답을 못 하면 탈락\n"
            "• 이미 나온 답을 말하면 탈락\n"
            "• 고민하는 시간도 3초에 포함!"
        )
        messages_to_reply = [TextMessage(text=text_msg)]
    elif user_text in ["!연상", "!연상게임"]:
        text_msg = (
            "🧠 연상게임\n\n"
            "제시된 단어를 보고\n"
            "가장 먼저 떠오르는 단어를 적어주세요!\n"
            "⌁┈┈┈┈⌁┈┈┈┈⌁┈┈┈┈⌁⌁┈┈┈┈⌁┈┈┈┈⌁┈┈┈┈⌁\n"
            "🏆 우승: 총점이 가장 높은 사람이 최종 우승!"
        )
        messages_to_reply = [TextMessage(text=text_msg)]
    elif user_text in ["/마디", "/마디수"]:
        count = user_data[user_id]['count']
        name = user_data[user_id]['display_name']
        messages_to_reply = [TextMessage(text=f"📊 {name}님의 현재 마디 수: {count}마디")]
    elif user_text == "/순위":
        sorted_users = sorted(user_data.values(), key=lambda x: x['count'], reverse=True)
        reply_text = "🏆 오늘의 마디 수 순위 🏆\n"
        for idx, user in enumerate(sorted_users, 1):
            reply_text += f"\n{idx}위. {user['display_name']} ({user['count']}개)"
        messages_to_reply = [TextMessage(text=reply_text)]
    elif user_text in ["/미달", "/경고", "/30마디"]:
        under_active = [u for u in user_data.values() if u['count'] < 30]
        if not under_active:
            reply_text = "🎉 모든 멤버가 30마디 이상 작성했습니다!"
        else:
            under_active.sort(key=lambda x: x['count'])
            reply_text = "⚠️ 30마디 미만 활동자 목록 ⚠️\n"
            for user in under_active:
                reply_text += f"\n• {user['display_name']}: {user['count']}마디 (총 미달 {user.get('total_under_count', 0)}회)"
        messages_to_reply = [TextMessage(text=reply_text)]
    elif user_text in ["/도움말", "/명령어"]:
        help_text = (
            "🤖 [마디 봇 명령어 안내]\n\n"
            "• /초대, /ㅊㄷ: 초대 인증\n"
            "• /담타, /ㄷㅌ: 담타 이미지\n"
            "• /눈팅, /ㄴㅌ: 눈팅 이미지\n"
            "• /마디: 내 마디 수 확인\n"
            "• /순위: 전체 마디 순위 확인\n"
            "• /미달: 30마디 미만 멤버 확인"
        )
        messages_to_reply = [TextMessage(text=help_text)]
    elif user_text == "/초기화":
        user_chat_counts[chat_key]['users'] = {}
        messages_to_reply = [TextMessage(text="🔄 현재 방의 데이터가 초기화되었습니다.")]
    else:
        user_data[user_id]['count'] += 1
        return

    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=messages_to_reply))
    except Exception:
        pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


import html
import time
from datetime import datetime
from io import BytesIO

from telegram import ParseMode, Update
from telegram.error import BadRequest, TelegramError, Unauthorized
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    Filters,
    MessageHandler,
    run_async,
)
from telegram.utils.helpers import mention_html

import SaitamaRobot.modules.sql.global_bans_sql as sql
from SaitamaRobot.modules.sql.users_sql import get_user_com_chats
from SaitamaRobot import (
    DEV_USERS,
    EVENT_LOGS,
    OWNER_ID,
    STRICT_GBAN,
    DRAGONS,
    SUPPORT_CHAT,
    SPAMWATCH_SUPPORT_CHAT,
    DEMONS,
    TIGERS,
    WOLVES,
    sw,
    dispatcher,
)
from SaitamaRobot.modules.helper_funcs.chat_status import (
    is_user_admin,
    support_plus,
    user_admin,
)
from SaitamaRobot.modules.helper_funcs.extraction import (
    extract_user,
    extract_user_and_text,
)
from SaitamaRobot.modules.helper_funcs.misc import send_to_list

GBAN_ENFORCE_GROUP = 6

GBAN_ERRORS = {
    "Người dùng là quản trị viên của cuộc trò chuyện",
    "Trò chuyện không tìm thấy",
    "Không đủ quyền hạn chế / không hạn chế thành viên trò chuyện",
    "User_not_participant",
    "Peer_id_invalid",
    "Group chat was deactivated",
    "Need to be inviter of a user to kick it from a basic group",
    "Chat_admin_required",
    "Chỉ người tạo một nhóm cơ bản mới có thể yêu cầu quản trị viên nhóm",
    "Channel_private",
    "Không có trong cuộc trò chuyện",
    "Không thể xóa chủ sở hữu cuộc trò chuyện",
}

UNGBAN_ERRORS = {
    "Người dùng là quản trị viên của cuộc trò chuyện",
    "Chat not found",
    "Không đủ quyền hạn chế / không hạn chế thành viên trò chuyện",
    "User_not_participant",
    "Phương pháp chỉ khả dụng cho các cuộc trò chuyện nhóm và kênh",
    "Not in the chat",
    "Channel_private",
    "Chat_admin_required",
    "Peer_id_invalid",
    "User not found",
}


@run_async
@support_plus
def gban(update: Update, context: CallbackContext):
    bot, args = context.bot, context.args
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    log_message = ""

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text(
            "Có vẻ như bạn không đề cập đến người dùng hoặc ID được chỉ định không chính xác ..",
        )
        return

    if int(user_id) in DEV_USERS:
        message.reply_text(
            "Người dùng đó là một phần của Hiệp hội.\nTôi không thể hành động chống lại chính mình.",
        )
        return

    if int(user_id) in DRAGONS:
        message.reply_text(
            "Tôi do thám, với con mắt nhỏ của mình ... một thảm họa! Tại sao các bạn lại bật nhau?",
        )
        return

    if int(user_id) in DEMONS:
        message.reply_text(
            "OOOH một người nào đó đang cố gắng gây ra một thảm họa ma quỷ! *grabs popcorn*",
        )
        return

    if int(user_id) in TIGERS:
        message.reply_text("That's a Tiger! They cannot be banned!")
        return

    if int(user_id) in WOLVES:
        message.reply_text("That's a Wolf! They cannot be banned!")
        return

    if user_id == bot.id:
        message.reply_text("Bạn uhh ... muốn tôi tự đấm mình?")
        return

    if user_id in [777000, 1087968824]:
        message.reply_text("Ngu xuẩn! Bạn không thể tấn công công nghệ gốc của Telegram!")
        return

    try:
        user_chat = bot.get_chat(user_id)
    except BadRequest as excp:
        if excp.message == "Không tìm thấy người dùng":
            message.reply_text("Tôi dường như không thể tìm thấy người dùng này.")
            return ""
        else:
            return

    if user_chat.type != "private":
        message.reply_text("Đó không phải là một người dùng!")
        return

    if sql.is_user_gbanned(user_id):

        if not reason:
            message.reply_text(
                "Người dùng này đã bị cấm; Tôi muốn thay đổi lý do, nhưng bạn chưa cho tôi ...",
            )
            return

        old_reason = sql.update_gban_reason(
            user_id, user_chat.username or user_chat.first_name, reason,
        )
        if old_reason:
            message.reply_text(
                "Người dùng này đã bị cấm, vì lý do sau:\n"
                "<code>{}</code>\n"
                "Tôi đã đi và cập nhật nó với lý do mới của bạn!".format(
                    html.escape(old_reason),
                ),
                parse_mode=ParseMode.HTML,
            )

        else:
            message.reply_text(
                "Người dùng này đã bị cấm, nhưng không có lý do nào được đặt ra; Tôi đã đi và cập nhật nó!",
            )

        return

    message.reply_text("Đang thêm vào Dead Note!")

    start_time = time.time()
    datetime_fmt = "%Y-%m-%dT%H:%M"
    current_time = datetime.utcnow().strftime(datetime_fmt)

    if chat.type != "private":
        chat_origin = "<b>{} ({})</b>\n".format(html.escape(chat.title), chat.id)
    else:
        chat_origin = "<b>{}</b>\n".format(chat.id)

    log_message = (
        f"#GBANNED\n"
        f"<b>Nguồn:</b> <code>{chat_origin}</code>\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"<b>Người dùng:</b> {mention_html(user_chat.id, user_chat.first_name)}\n"
        f"<b>ID:</b> <code>{user_chat.id}</code>\n"
        f"<b>Vào lúc:</b> <code>{current_time}</code>"
    )

    if reason:
        if chat.type == chat.SUPERGROUP and chat.username:
            log_message += f'\n<b>Reason:</b> <a href="https://telegram.me/{chat.username}/{message.message_id}">{reason}</a>'
        else:
            log_message += f"\n<b>Reason:</b> <code>{reason}</code>"

    if EVENT_LOGS:
        try:
            log = bot.send_message(EVENT_LOGS, log_message, parse_mode=ParseMode.HTML)
        except BadRequest as excp:
            log = bot.send_message(
                EVENT_LOGS,
                log_message
                + "\n\nĐịnh dạng đã bị vô hiệu hóa do lỗi không mong muốn.",
            )

    else:
        send_to_list(bot, DRAGONS + DEMONS, log_message, html=True)

    sql.gban_user(user_id, user_chat.username or user_chat.first_name, reason)

    chats = get_user_com_chats(user_id)
    gbanned_chats = 0

    for chat in chats:
        chat_id = int(chat)

        # Check if this group has disabled gbans
        if not sql.does_chat_gban(chat_id):
            continue

        try:
            bot.kick_chat_member(chat_id, user_id)
            gbanned_chats += 1

        except BadRequest as excp:
            if excp.message in GBAN_ERRORS:
                pass
            else:
                message.reply_text(f"Could not gban due to: {excp.message}")
                if EVENT_LOGS:
                    bot.send_message(
                        EVENT_LOGS,
                        f"Could not gban due to {excp.message}",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    send_to_list(
                        bot, DRAGONS + DEMONS, f"Could not gban due to: {excp.message}",
                    )
                sql.ungban_user(user_id)
                return
        except TelegramError:
            pass

    if EVENT_LOGS:
        log.edit_text(
            log_message + f"\n<b>Đã cấm tổng:</b> <code>{gbanned_chats}</code> nhóm",
            parse_mode=ParseMode.HTML,
        )
    else:
        send_to_list(
            bot,
            DRAGONS + DEMONS,
            f"Done! (Đã cấm khỏi <code>{gbanned_chats}</code> nhóm)",
            html=True,
        )

    end_time = time.time()
    gban_time = round((end_time - start_time), 2)

    if gban_time > 60:
        gban_time = round((gban_time / 60), 2)
        message.reply_text("Done! Đã cho vào Dead Note.", parse_mode=ParseMode.HTML)
    else:
        message.reply_text("Done! Đã cho vào Dead Note.", parse_mode=ParseMode.HTML)

    try:
        bot.send_message(
            user_id,
            "#EVENT"
            "Bạn đã bị đánh dấu là Độc hại và do đó đã bị cấm tham gia vào bất kỳ nhóm nào trong tương lai mà chúng tôi quản lý."
            f"\n<b>Lý do:</b> <code>{html.escape(user.reason)}</code>"
            f"</b>Khiếu nại:</b> @{SUPPORT_CHAT}",
            parse_mode=ParseMode.HTML,
        )
    except:
        pass  # bot probably blocked by user


@run_async
@support_plus
def ungban(update: Update, context: CallbackContext):
    bot, args = context.bot, context.args
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    log_message = ""

    user_id = extract_user(message, args)

    if not user_id:
        message.reply_text(
            "Có vẻ như bạn không đề cập đến người dùng hoặc ID được chỉ định không chính xác ..",
        )
        return

    user_chat = bot.get_chat(user_id)
    if user_chat.type != "private":
        message.reply_text("Đó không phải là một người dùng!")
        return

    if not sql.is_user_gbanned(user_id):
        message.reply_text("Người dùng này không bị cấm!")
        return

    message.reply_text(f"Em sẽ cho {user_chat.first_name} cơ hội thứ hai, trên toàn cầu.")

    start_time = time.time()
    datetime_fmt = "%Y-%m-%dT%H:%M"
    current_time = datetime.utcnow().strftime(datetime_fmt)

    if chat.type != "private":
        chat_origin = f"<b>{html.escape(chat.title)} ({chat.id})</b>\n"
    else:
        chat_origin = f"<b>{chat.id}</b>\n"

    log_message = (
        f"#UNGBANNED\n"
        f"<b>Có nguồn gốc từ:</b> <code>{chat_origin}</code>\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"<b>Bỏ cấm::</b> {mention_html(user_chat.id, user_chat.first_name)}\n"
        f"<b>ID:</b> <code>{user_chat.id}</code>\n"
        f"<b>Thời gian:</b> <code>{current_time}</code>"
    )

    if EVENT_LOGS:
        try:
            log = bot.send_message(EVENT_LOGS, log_message, parse_mode=ParseMode.HTML)
        except BadRequest as excp:
            log = bot.send_message(
                EVENT_LOGS,
                log_message
                + "\n\nĐịnh dạng đã bị vô hiệu hóa do lỗi không mong muốn.",
            )
    else:
        send_to_list(bot, DRAGONS + DEMONS, log_message, html=True)

    chats = get_user_com_chats(user_id)
    ungbanned_chats = 0

    for chat in chats:
        chat_id = int(chat)

        # Check if this group has disabled gbans
        if not sql.does_chat_gban(chat_id):
            continue

        try:
            member = bot.get_chat_member(chat_id, user_id)
            if member.status == "kicked":
                bot.unban_chat_member(chat_id, user_id)
                ungbanned_chats += 1

        except BadRequest as excp:
            if excp.message in UNGBAN_ERRORS:
                pass
            else:
                message.reply_text(f"Không thể hủy gban do: {excp.message}")
                if EVENT_LOGS:
                    bot.send_message(
                        EVENT_LOGS,
                        f"Không thể hủy gban do: {excp.message}",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    bot.send_message(
                        OWNER_ID, f"Không thể hủy gban do: {excp.message}",
                    )
                return
        except TelegramError:
            pass

    sql.ungban_user(user_id)

    if EVENT_LOGS:
        log.edit_text(
            log_message + f"\n<b>Nhóm bị ảnh hưởng:</b> {ungbanned_chats}",
            parse_mode=ParseMode.HTML,
        )
    else:
        send_to_list(bot, DRAGONS + DEMONS, "hoàn thành un-gban!")

    end_time = time.time()
    ungban_time = round((end_time - start_time), 2)

    if ungban_time > 60:
        ungban_time = round((ungban_time / 60), 2)
        message.reply_text(f"Người đã được bỏ cấm. Trong {ungban_time} phút")
    else:
        message.reply_text(f"Người đã được bỏ cấm. Trong {ungban_time} giây")


@run_async
@support_plus
def gbanlist(update: Update, context: CallbackContext):
    banned_users = sql.get_gban_list()

    if not banned_users:
        update.effective_message.reply_text(
            "Không có bất kỳ người dùng nào bị cấm! Bạn tốt hơn tôi mong đợi ...",
        )
        return

    banfile = "Vặn những kẻ này.\n"
    for user in banned_users:
        banfile += f"[x] {user['name']} - {user['user_id']}\n"
        if user["reason"]:
            banfile += f"Lý do: {user['reason']}\n"

    with BytesIO(str.encode(banfile)) as output:
        output.name = "gbanlist.txt"
        update.effective_message.reply_document(
            document=output,
            filename="gbanlist.txt",
            caption="Đây là danh sách những người dùng bị cấm.",
        )


def check_and_ban(update, user_id, should_message=True):
    
    chat = update.effective_chat  # type: Optional[Chat]
    try:
        sw_ban = sw.get_ban(int(user_id))
    except:
        sw_ban = None

    if sw_ban:
        update.effective_chat.kick_member(user_id)
        if should_message:
            update.effective_message.reply_text(
                f"<b>Cảnh báo</b>: Tội đồ vào nhóm.\n"
                f"<code>*đã sút vào mặt nó*</code>.\n"
                f"<b>Khiếu nại</b>: {SUPPORT_CHAT}\n"
                f"<b>ID</b>: <code>{sw_ban.id}</code>\n"
                f"<b>Lý do</b>: <code>{html.escape(sw_ban.reason)}</code>",
                parse_mode=ParseMode.HTML,
            )
        return

    if sql.is_user_gbanned(user_id):
        update.effective_chat.kick_member(user_id)
        if should_message:
            text = (
                f"<b>CẢNH BÁO TỘI ĐỒ VÀO NHÓM!/b>\n"
                f"<code>*đã sút thẳng vào mồm nó*</code>.\n"
                f"<b>Khiếu nại</b>: @{SUPPORT_CHAT}\n"
                f"<b>User ID</b>: <code>{user_id}</code>"
            )
            user = sql.get_gbanned_user(user_id)
            if user.reason:
                text += f"\n<b>Lý do:</b> <code>{html.escape(user.reason)}</code>"
            update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


@run_async
def enforce_gban(update: Update, context: CallbackContext):
    # Not using @restrict handler to avoid spamming - just ignore if cant gban.
    bot = context.bot
    try:
        restrict_permission = update.effective_chat.get_member(
            bot.id,
        ).can_restrict_members
    except Unauthorized:
        return
    if sql.does_chat_gban(update.effective_chat.id) and restrict_permission:
        user = update.effective_user
        chat = update.effective_chat
        msg = update.effective_message

        if user and not is_user_admin(chat, user.id):
            check_and_ban(update, user.id)
            return

        if msg.new_chat_members:
            new_members = update.effective_message.new_chat_members
            for mem in new_members:
                check_and_ban(update, mem.id)

        if msg.reply_to_message:
            user = msg.reply_to_message.from_user
            if user and not is_user_admin(chat, user.id):
                check_and_ban(update, user.id, should_message=False)


@run_async
@user_admin
def gbanstat(update: Update, context: CallbackContext):
    args = context.args
    if len(args) > 0:
        if args[0].lower() in ["on", "yes"]:
            sql.enable_gbans(update.effective_chat.id)
            update.effective_message.reply_text(
                "Antispam hiện đã được bật ✅ "
                "Tôi hiện đang bảo vệ nhóm của bạn khỏi các mối đe dọa tiềm ẩn từ xa!",
            )
        elif args[0].lower() in ["off", "no"]:
            sql.disable_gbans(update.effective_chat.id)
            update.effective_message.reply_text(
                "Antispan hiện đã bị vô hiệu hóa ❌ " "Spamwatch hiện đã bị vô hiệu hóa ❌",
            )
    else:
        update.effective_message.reply_text(
            "Hãy cho tôi một số đối số để chọn một thiết lập! on/off, yes/no!\n\n"
            "Cài đặt hiện tại của bạn là: {}\n"
            "Khi True, bất kỳ gbans nào xảy ra cũng sẽ xảy ra trong nhóm của bạn. "
            "Khi False, họ sẽ không làm gì, bỏ mặc bạn với sự thương xót có thể"
            " người gửi thư rác.".format(sql.does_chat_gban(update.effective_chat.id)),
        )


def __stats__():
    return f"• {sql.num_gbanned_users()} gbanned users."


def __user_info__(user_id):
    is_gbanned = sql.is_user_gbanned(user_id)
    text = "Độc hại: <b>{}</b>"
    if user_id in [777000, 1087968824]:
        return ""
    if user_id == dispatcher.bot.id:
        return ""
    if int(user_id) in DRAGONS + TIGERS + WOLVES:
        return ""
    if is_gbanned:
        text = text.format("Yes")
        user = sql.get_gbanned_user(user_id)
        if user.reason:
            text += f"\n<b>Lý do:</b> <code>{html.escape(user.reason)}</code>"
        text += f"\n<b>Khiếu nại:</b> @{SUPPORT_CHAT}"
    else:
        text = text.format("???")
    return text


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    return f"Cuộc trò chuyện này đang thực thi *gbans*: `{sql.does_chat_gban(chat_id)}`."


__help__ = f"""
*Admins only:*
 • `/antispam <on/off/yes/no>`*:* Will toggle our antispam tech or return your current settings.

Chống thư rác, được sử dụng bởi các nhà phát triển bot để cấm những người gửi thư rác trên tất cả các nhóm. Điều này giúp bảo vệ \
bạn và các nhóm của bạn bằng cách loại bỏ lũ spam càng nhanh càng tốt.
*Lưu ý:* Người dùng có thể khiếu nại các gbans hoặc báo cáo những kẻ gửi spam tại @{SUPPORT_CHAT}

Điều này cũng tích hợp API @Spamwatch để loại bỏ Người gửi spam khỏi phòng trò chuyện của bạn nhiều nhất có thể!
*SpamWatch là gì?*
SpamWatch duy trì một danh sách cấm cập nhật liên tục lớn gồm spam bots, troll, người gửi thư rác bitcoin và các ký tự không đáng tin cậy[.](https://telegra.ph/file/f584b643c6f4be0b1de53.jpg)
Không ngừng giúp đỡ tự động cấm những người gửi thư rác khỏi nhóm của bạn Vì vậy, bạn sẽ không phải lo lắng về việc những người gửi thư rác tấn công nhóm của bạn.
*Lưu ý:* Người dùng có thể khiếu nại các spamwatch tại @SpamwatchSupport
"""

GBAN_HANDLER = CommandHandler("gban", gban)
UNGBAN_HANDLER = CommandHandler("ungban", ungban)
GBAN_LIST = CommandHandler("gbanlist", gbanlist)

GBAN_STATUS = CommandHandler("antispam", gbanstat, filters=Filters.group)

GBAN_ENFORCER = MessageHandler(Filters.all & Filters.group, enforce_gban)

dispatcher.add_handler(GBAN_HANDLER)
dispatcher.add_handler(UNGBAN_HANDLER)
dispatcher.add_handler(GBAN_LIST)
dispatcher.add_handler(GBAN_STATUS)

__mod_name__ = "Ẩn sát"
__handlers__ = [GBAN_HANDLER, UNGBAN_HANDLER, GBAN_LIST, GBAN_STATUS]

if STRICT_GBAN:  # enforce GBANS if this is set
    dispatcher.add_handler(GBAN_ENFORCER, GBAN_ENFORCE_GROUP)
    __handlers__.append((GBAN_ENFORCER, GBAN_ENFORCE_GROUP))

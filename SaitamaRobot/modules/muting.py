import html
from typing import Optional

from SaitamaRobot import LOGGER, TIGERS, dispatcher
from SaitamaRobot.modules.helper_funcs.chat_status import (
    bot_admin,
    can_restrict,
    connection_status,
    is_user_admin,
    user_admin,
)
from SaitamaRobot.modules.helper_funcs.extraction import (
    extract_user,
    extract_user_and_text,
)
from SaitamaRobot.modules.helper_funcs.string_handling import extract_time
from SaitamaRobot.modules.log_channel import loggable
from telegram import Bot, Chat, ChatPermissions, ParseMode, Update
from telegram.error import BadRequest
from telegram.ext import CallbackContext, CommandHandler, run_async
from telegram.utils.helpers import mention_html


def check_user(user_id: int, bot: Bot, chat: Chat) -> Optional[str]:
    if not user_id:
        reply = "Có vẻ như bạn không đề cập đến người dùng hoặc ID được chỉ định không chính xác..."
        return reply

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "Không tìm thấy người dùng":
            reply = "Tôi dường như không thể tìm thấy người dùng này"
            return reply
        else:
            raise

    if user_id == bot.id:
        reply = "I'm not gonna MUTE myself, How high are you?"
        return reply

    if is_user_admin(chat, user_id, member) or user_id in TIGERS:
        reply = "Can't. Find someone else to mute but not this one."
        return reply

    return None


@run_async
@connection_status
@bot_admin
@user_admin
@loggable
def mute(update: Update, context: CallbackContext) -> str:
    bot = context.bot
    args = context.args

    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    user_id, reason = extract_user_and_text(message, args)
    reply = check_user(user_id, bot, chat)

    if reply:
        message.reply_text(reply)
        return ""

    member = chat.get_member(user_id)

    log = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#MUTE\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}"
    )

    if reason:
        log += f"\n<b>Reason:</b> {reason}"

    if member.can_send_messages is None or member.can_send_messages:
        chat_permissions = ChatPermissions(can_send_messages=False)
        bot.restrict_chat_member(chat.id, user_id, chat_permissions)
        bot.sendMessage(
            chat.id,
            "{} đã bị khóa mõm bởi {}\n<b>Lý do</b>: {}".format(
                mention_html(member.user.id, member.user.first_name), mention_html(user.id, user.first_name), reason
            ),
            parse_mode=ParseMode.HTML,
        )
        return log

    else:
        message.reply_text("Đã khóa mõm nó!")

    return ""


@run_async
@connection_status
@bot_admin
@user_admin
@loggable
def unmute(update: Update, context: CallbackContext) -> str:
    bot, args = context.bot, context.args
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text(
            "Bạn sẽ cần cung cấp cho tôi tên người dùng để hiển thị hoặc trả lời một người nào đó để được hiển thị.",
        )
        return ""

    member = chat.get_member(int(user_id))

    if member.status != "kicked" and member.status != "left":
        if (
            member.can_send_messages
            and member.can_send_media_messages
            and member.can_send_other_messages
            and member.can_add_web_page_previews
        ):
            message.reply_text("Người dùng này đã có quyền nói.")
        else:
            chat_permissions = ChatPermissions(
                can_send_messages=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_send_polls=True,
                can_change_info=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            )
            try:
                bot.restrict_chat_member(chat.id, int(user_id), chat_permissions)
            except BadRequest:
                pass
            bot.sendMessage(
                chat.id,
                f"Chị tạm tha nhé bé <b>{html.escape(member.user.first_name)}</b>, liệu hồn với chị đấy!",
                parse_mode=ParseMode.HTML,
            )
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"#UNMUTE\n"
                f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}"
            )
    else:
        message.reply_text(
            "Người dùng này thậm chí không tham gia cuộc trò chuyện, việc bật tiếng họ sẽ không khiến họ nói nhiều hơn họ "
            "đã làm!",
        )

    return ""


@run_async
@connection_status
@bot_admin
@can_restrict
@user_admin
@loggable
def temp_mute(update: Update, context: CallbackContext) -> str:
    bot, args = context.bot, context.args
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    user_id, reason = extract_user_and_text(message, args)
    reply = check_user(user_id, bot, chat)

    if reply:
        message.reply_text(reply)
        return ""

    member = chat.get_member(user_id)

    if not reason:
        message.reply_text("Bạn chưa chỉ định thời gian để tắt tiếng người dùng này!")
        return ""

    split_reason = reason.split(None, 1)

    time_val = split_reason[0].lower()
    if len(split_reason) > 1:
        reason = split_reason[1]
    else:
        reason = ""

    mutetime = extract_time(message, time_val)

    if not mutetime:
        return ""

    log = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#TEMP MUTED\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}\n"
        f"<b>Time:</b> {time_val}"
    )
    if reason:
        log += f"\n<b>Reason:</b> {reason}"

    try:
        if member.can_send_messages is None or member.can_send_messages:
            chat_permissions = ChatPermissions(can_send_messages=False)
            bot.restrict_chat_member(
                chat.id, user_id, chat_permissions, until_date=mutetime,
            )
            bot.sendMessage(
                chat.id,
                f"Thôi thôi, <b>{html.escape(member.user.first_name)}</b> tạm thời bị rọ mõm trong {time_val} nhá!",
                parse_mode=ParseMode.HTML,
            )
            return log
        else:
            message.reply_text("Đã đeo rọ mõm cho nó.")

    except BadRequest as excp:
        if excp.message == "Trả lời tin nhắn không tìm thấy":
            # Do not reply
            message.reply_text(f"Đeo rõ mõm trong {time_val}!", quote=False)
            return log
        else:
            LOGGER.warning(update)
            LOGGER.exception(
                "ERROR muting user %s in chat %s (%s) due to %s",
                user_id,
                chat.title,
                chat.id,
                excp.message,
            )
            message.reply_text("Well damn, I can't mute that user.")

    return ""


__help__ = """
*Admins only:*
 • `/khoamom <userhandle>`*:* người dùng im lặng. Cũng có thể được sử dụng như một câu trả lời, tắt tiếng người dùng đã trả lời.
 • `/tamkhoa <userhandle> x(m/h/d)`*:* tắt tiếng người dùng trong x thời gian. (qua tay cầm hoặc trả lời). `m` = `minutes`, `h` = `hours`, `d` = `days`.
 • `/tatkhoamom <userhandle>`*:* bật tiếng người dùng. Cũng có thể được sử dụng như một câu trả lời, tắt tiếng người dùng đã trả lời.
"""

MUTE_HANDLER = CommandHandler("khoamom", mute)
UNMUTE_HANDLER = CommandHandler("tatkhoamom", unmute)
TEMPMUTE_HANDLER = CommandHandler(["tmute", "tamkhoamom"], temp_mute)

dispatcher.add_handler(MUTE_HANDLER)
dispatcher.add_handler(UNMUTE_HANDLER)
dispatcher.add_handler(TEMPMUTE_HANDLER)

__mod_name__ = "Khóa mõm"
__handlers__ = [MUTE_HANDLER, UNMUTE_HANDLER, TEMPMUTE_HANDLER]

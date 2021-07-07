import html

from SaitamaRobot import LOGGER, DRAGONS, TIGERS, WOLVES, dispatcher
from SaitamaRobot.modules.helper_funcs.chat_status import user_admin, user_not_admin
from SaitamaRobot.modules.log_channel import loggable
from SaitamaRobot.modules.sql import reporting_sql as sql
from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Update
from telegram.error import BadRequest, Unauthorized
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    Filters,
    MessageHandler,
    run_async,
)
from telegram.utils.helpers import mention_html

REPORT_GROUP = 12
REPORT_IMMUNE_USERS = DRAGONS + TIGERS + WOLVES


@run_async
@user_admin
def report_setting(update: Update, context: CallbackContext):
    bot, args = context.bot, context.args
    chat = update.effective_chat
    msg = update.effective_message

    if chat.type == chat.PRIVATE:
        if len(args) >= 1:
            if args[0] in ("yes", "on"):
                sql.set_user_setting(chat.id, True)
                msg.reply_text(
                    "Đã bật báo cáo! Bạn sẽ được thông báo bất cứ khi nào có ai đó báo cáo điều gì đó.",
                )

            elif args[0] in ("no", "off"):
                sql.set_user_setting(chat.id, False)
                msg.reply_text("Đã tắt báo cáo! Bạn sẽ không nhận được bất kỳ báo cáo nào.")
        else:
            msg.reply_text(
                f"Tùy chọn báo cáo hiện tại của bạn là: `{sql.user_should_report(chat.id)}`",
                parse_mode=ParseMode.MARKDOWN,
            )

    else:
        if len(args) >= 1:
            if args[0] in ("yes", "on"):
                sql.set_chat_setting(chat.id, True)
                msg.reply_text(
                    "Đã bật báo cáo! Quản trị viên đã bật báo cáo sẽ được thông báo khi /baocao "
                    "hoặc @but",
                )

            elif args[0] in ("no", "off"):
                sql.set_chat_setting(chat.id, False)
                msg.reply_text(
                    "Đã tắt báo cáo! Sẽ không có quản trị viên nào được thông báo về /baocao hoặc @but.",
                )
        else:
            msg.reply_text(
                f"Cài đặt hiện tại của nhóm này là: `{sql.chat_should_report(chat.id)}`",
                parse_mode=ParseMode.MARKDOWN,
            )


@run_async
@user_not_admin
@loggable
def report(update: Update, context: CallbackContext) -> str:
    bot = context.bot
    args = context.args
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if chat and message.reply_to_message and sql.chat_should_report(chat.id):
        reported_user = message.reply_to_message.from_user
        chat_name = chat.title or chat.first or chat.username
        admin_list = chat.get_administrators()
        message = update.effective_message

        if not args:
            message.reply_text("Thêm lý do báo cáo trước.")
            return ""

        if user.id == reported_user.id:
            message.reply_text("Oke, cảm ơn bạn đã báo cáo với quản trị viên!")
            return ""

        if user.id == bot.id:
            message.reply_text("Rất tốt.")
            return ""

        if reported_user.id in REPORT_IMMUNE_USERS:
            message.reply_text("Ờ? Bạn đang báo cáo một thảm họa?")
            return ""

        if chat.username and chat.type == Chat.SUPERGROUP:

            reported = f"{mention_html(user.id, user.first_name)} đã báo cáo {mention_html(reported_user.id, reported_user.first_name)} với quản trị viên!"

            msg = (
                f"<b>⚠️ Báo cáo: </b>{html.escape(chat.title)}\n"
                f"<b> • Báo cáo bởi:</b> {mention_html(user.id, user.first_name)}(<code>{user.id}</code>)\n"
                f"<b> • Người bị báo cáo:</b> {mention_html(reported_user.id, reported_user.first_name)} (<code>{reported_user.id}</code>)\n"
            )
            link = f'<b> • Tin nhắn báo cáo:</b> <a href="https://t.me/{chat.username}/{message.reply_to_message.message_id}">xem thử</a>'
            should_forward = False
            keyboard = [
                [
                    InlineKeyboardButton(
                        "➡ Xem tin nhắn",
                        url=f"https://t.me/{chat.username}/{message.reply_to_message.message_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "⚠ Đá",
                        callback_data=f"report_{chat.id}=kick={reported_user.id}={reported_user.first_name}",
                    ),
                    InlineKeyboardButton(
                        "⛔️ Cấm",
                        callback_data=f"report_{chat.id}=banned={reported_user.id}={reported_user.first_name}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "❎ Xóa tin nhắn",
                        callback_data=f"report_{chat.id}=delete={reported_user.id}={message.reply_to_message.message_id}",
                    ),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            reported = (
                f"{mention_html(user.id, user.first_name)} đã báo cáo "
                f"{mention_html(reported_user.id, reported_user.first_name)} đến quản trị viên!"
            )

            msg = f'{mention_html(user.id, user.first_name)} đang kêu gọi quản trị viên trong "{html.escape(chat_name)}"!'
            link = ""
            should_forward = True

        for admin in admin_list:
            if admin.user.is_bot:  # can't message bots
                continue

            if sql.user_should_report(admin.user.id):
                try:
                    if not chat.type == Chat.SUPERGROUP:
                        bot.send_message(
                            admin.user.id, msg + link, parse_mode=ParseMode.HTML,
                        )

                        if should_forward:
                            message.reply_to_message.forward(admin.user.id)

                            if (
                                len(message.text.split()) > 1
                            ):  # If user is giving a reason, send his message too
                                message.forward(admin.user.id)
                    if not chat.username:
                        bot.send_message(
                            admin.user.id, msg + link, parse_mode=ParseMode.HTML,
                        )

                        if should_forward:
                            message.reply_to_message.forward(admin.user.id)

                            if (
                                len(message.text.split()) > 1
                            ):  # If user is giving a reason, send his message too
                                message.forward(admin.user.id)

                    if chat.username and chat.type == Chat.SUPERGROUP:
                        bot.send_message(
                            admin.user.id,
                            msg + link,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup,
                        )

                        if should_forward:
                            message.reply_to_message.forward(admin.user.id)

                            if (
                                len(message.text.split()) > 1
                            ):  # If user is giving a reason, send his message too
                                message.forward(admin.user.id)

                except Unauthorized:
                    pass
                except BadRequest as excp:  # TODO: cleanup exceptions
                    LOGGER.exception("Ngoại lệ trong khi báo cáo người dùng")

        message.reply_to_message.reply_text(
            f"{mention_html(user.id, user.first_name)} đã báo cáo tin nhắn cho các quản trị viên.",
            parse_mode=ParseMode.HTML,
        )
        return msg

    return ""


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, _):
    return f"Trò chuyện này được thiết lập để gửi báo cáo của người dùng cho quản trị viên, thông qua /report và @admin: `{sql.chat_should_report(chat_id)}`"


def __user_settings__(user_id):
    if sql.user_should_report(user_id) is True:
        text = "Bạn sẽ nhận được báo cáo từ các cuộc trò chuyện mà bạn là quản trị viên."
    else:
        text = "Bạn sẽ *không* nhận được báo cáo từ các cuộc trò chuyện mà bạn là quản trị viên."
    return text


def buttons(update: Update, context: CallbackContext):
    bot = context.bot
    query = update.callback_query
    splitter = query.data.replace("report_", "").split("=")
    if splitter[1] == "kick":
        try:
            bot.kickChatMember(splitter[0], splitter[2])
            bot.unbanChatMember(splitter[0], splitter[2])
            query.answer("✅ Đã đá thành công")
            return ""
        except Exception as err:
            query.answer("🛑 Đá người dùng thất bại")
            bot.sendMessage(
                text=f"Lỗi: {err}",
                chat_id=query.message.chat_id,
                parse_mode=ParseMode.HTML,
            )
    elif splitter[1] == "banned":
        try:
            bot.kickChatMember(splitter[0], splitter[2])
            query.answer("✅  Đã cấm người dùng")
            return ""
        except Exception as err:
            bot.sendMessage(
                text=f"Lỗi: {err}",
                chat_id=query.message.chat_id,
                parse_mode=ParseMode.HTML,
            )
            query.answer("🛑 Cấm thất bại")
    elif splitter[1] == "delete":
        try:
            bot.deleteMessage(splitter[0], splitter[3])
            query.answer("✅ Đã xóa tin nhắn")
            return ""
        except Exception as err:
            bot.sendMessage(
                text=f"Error: {err}",
                chat_id=query.message.chat_id,
                parse_mode=ParseMode.HTML,
            )
            query.answer("🛑 Không thể xóa tin nhắn!")


__help__ = """
 • `/baocao <lý do báo cáo>`*:* trả lời tin nhắn để báo cáo cho quản trị viên.
 • `@but`*:* trả lời tin nhắn để báo cáo cho quản trị viên.
*LƯU Ý:* Cả hai điều này sẽ không được kích hoạt nếu được quản trị viên sử dụng.

*Admins only:*
 • `/caibaocao <on/off>`*:* thay đổi cài đặt báo cáo hoặc xem trạng thái hiện tại.
   • Nếu được thực hiện vào buổi chiều, hãy chuyển trạng thái của bạn.
   • Nếu ở trong nhóm, hãy chuyển đổi trạng thái của nhóm đó.
"""

SETTING_HANDLER = CommandHandler("caibaocao", report_setting)
REPORT_HANDLER = CommandHandler("baocao", report, filters=Filters.group)
ADMIN_REPORT_HANDLER = MessageHandler(Filters.regex(r"(?i)@but(s)?"), report)

REPORT_BUTTON_USER_HANDLER = CallbackQueryHandler(buttons, pattern=r"report_")
dispatcher.add_handler(REPORT_BUTTON_USER_HANDLER)

dispatcher.add_handler(SETTING_HANDLER)
dispatcher.add_handler(REPORT_HANDLER, REPORT_GROUP)
dispatcher.add_handler(ADMIN_REPORT_HANDLER, REPORT_GROUP)

__mod_name__ = "Báo cáo"
__handlers__ = [
    (REPORT_HANDLER, REPORT_GROUP),
    (ADMIN_REPORT_HANDLER, REPORT_GROUP),
    (SETTING_HANDLER),
]

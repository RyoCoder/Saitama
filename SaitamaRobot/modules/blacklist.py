import html
import re

from telegram import ParseMode, ChatPermissions
from telegram.error import BadRequest
from telegram.ext import CommandHandler, MessageHandler, Filters, run_async
from telegram.utils.helpers import mention_html

import SaitamaRobot.modules.sql.blacklist_sql as sql
from SaitamaRobot import dispatcher, LOGGER
from SaitamaRobot.modules.disable import DisableAbleCommandHandler
from SaitamaRobot.modules.helper_funcs.chat_status import user_admin, user_not_admin
from SaitamaRobot.modules.helper_funcs.extraction import extract_text
from SaitamaRobot.modules.helper_funcs.misc import split_message
from SaitamaRobot.modules.log_channel import loggable
from SaitamaRobot.modules.warns import warn
from SaitamaRobot.modules.helper_funcs.string_handling import extract_time
from SaitamaRobot.modules.connection import connected
from SaitamaRobot.modules.sql.approve_sql import is_approved
from SaitamaRobot.modules.helper_funcs.alternate import send_message, typing_action

BLACKLIST_GROUP = 11


@run_async
@user_admin
@typing_action
def blacklist(update, context):
    chat = update.effective_chat
    user = update.effective_user
    args = context.args

    conn = connected(context.bot, update, chat, user.id, need_admin=False)
    if conn:
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if chat.type == "private":
            return
        chat_id = update.effective_chat.id
        chat_name = chat.title

    filter_list = "Current blacklisted words in <b>{}</b>:\n".format(chat_name)

    all_blacklisted = sql.get_chat_blacklist(chat_id)

    if len(args) > 0 and args[0].lower() == "copy":
        for trigger in all_blacklisted:
            filter_list += "<code>{}</code>\n".format(html.escape(trigger))
    else:
        for trigger in all_blacklisted:
            filter_list += " - <code>{}</code>\n".format(html.escape(trigger))

    # for trigger in all_blacklisted:
    #     filter_list += " - <code>{}</code>\n".format(html.escape(trigger))

    split_text = split_message(filter_list)
    for text in split_text:
        if filter_list == "Các từ được đưa vào danh sách đen hiện tại trong <b>{}</b>:\n".format(
            html.escape(chat_name),
        ):
            send_message(
                update.effective_message,
                "Không có từ nào trong danh sách đen ở <b>{}</b>!".format(html.escape(chat_name)),
                parse_mode=ParseMode.HTML,
            )
            return
        send_message(update.effective_message, text, parse_mode=ParseMode.HTML)


@run_async
@user_admin
@typing_action
def add_blacklist(update, context):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    words = msg.text.split(None, 1)

    conn = connected(context.bot, update, chat, user.id)
    if conn:
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            return
        else:
            chat_name = chat.title

    if len(words) > 1:
        text = words[1]
        to_blacklist = list(
            {trigger.strip() for trigger in text.split("\n") if trigger.strip()},
        )
        for trigger in to_blacklist:
            sql.add_to_blacklist(chat_id, trigger.lower())

        if len(to_blacklist) == 1:
            send_message(
                update.effective_message,
                "Đã thêm từ khóa vào danh sách đen trong chat: <b>{}</b>!".format(
                    html.escape(chat_name),
                ),
                parse_mode=ParseMode.HTML,
            )

        else:
            send_message(
                update.effective_message,
                "Đã thêm trình kích hoạt danh sách đen: <code>{}</code> trong <b>{}</b>!".format(
                    len(to_blacklist), html.escape(chat_name),
                ),
                parse_mode=ParseMode.HTML,
            )

    else:
        send_message(
            update.effective_message,
            "Hãy cho tôi biết bạn muốn thêm từ nào vào danh sách đen.",
        )


@run_async
@user_admin
@typing_action
def unblacklist(update, context):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    words = msg.text.split(None, 1)

    conn = connected(context.bot, update, chat, user.id)
    if conn:
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            return
        else:
            chat_name = chat.title

    if len(words) > 1:
        text = words[1]
        to_unblacklist = list(
            {trigger.strip() for trigger in text.split("\n") if trigger.strip()},
        )
        successful = 0
        for trigger in to_unblacklist:
            success = sql.rm_from_blacklist(chat_id, trigger.lower())
            if success:
                successful += 1

        if len(to_unblacklist) == 1:
            if successful:
                send_message(
                    update.effective_message,
                    "Đã xóa <code>{}</code> khỏi danh sách đen trong <b>{}</b>!".format(
                        html.escape(to_unblacklist[0]), html.escape(chat_name),
                    ),
                    parse_mode=ParseMode.HTML,
                )
            else:
                send_message(
                    update.effective_message, "Đây không phải là một kích hoạt danh sách đen!",
                )

        elif successful == len(to_unblacklist):
            send_message(
                update.effective_message,
                "Đã xóa <code>{}</code> khỏi danh sách đen trong <b>{}</b>!".format(
                    successful, html.escape(chat_name),
                ),
                parse_mode=ParseMode.HTML,
            )

        elif not successful:
            send_message(
                update.effective_message,
                "Không có trình kích hoạt nào trong số này tồn tại nên không thể loại bỏ nó.",
                parse_mode=ParseMode.HTML,
            )

        else:
            send_message(
                update.effective_message,
                "Removed <code>{}</code> from blacklist. {} did not exist, "
                "so were not removed.".format(
                    successful, len(to_unblacklist) - successful,
                ),
                parse_mode=ParseMode.HTML,
            )
    else:
        send_message(
            update.effective_message,
            "Tell me which words you would like to remove from blacklist!",
        )


@run_async
@loggable
@user_admin
@typing_action
def blacklist_mode(update, context):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(
                update.effective_message,
                "This command can be only used in group not in PM",
            )
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    if args:
        if args[0].lower() in ["off", "nothing", "no"]:
            settypeblacklist = "không làm gì cả"
            sql.set_blacklist_strength(chat_id, 0, "0")
        elif args[0].lower() in ["del", "delete"]:
            settypeblacklist = "xóa tin nhắn trong danh sách đen"
            sql.set_blacklist_strength(chat_id, 1, "0")
        elif args[0].lower() == "warn":
            settypeblacklist = "cảnh báo người gửi"
            sql.set_blacklist_strength(chat_id, 2, "0")
        elif args[0].lower() == "mute":
            settypeblacklist = "khóa mõm người gửi"
            sql.set_blacklist_strength(chat_id, 3, "0")
        elif args[0].lower() == "kick":
            settypeblacklist = "đá người gửi"
            sql.set_blacklist_strength(chat_id, 4, "0")
        elif args[0].lower() == "ban":
            settypeblacklist = "sút người gửi"
            sql.set_blacklist_strength(chat_id, 5, "0")
        elif args[0].lower() == "tạm cấm người gửi":
            if len(args) == 1:
                teks = """Có vẻ như bạn đã cố gắng đặt giá trị thời gian cho danh sách đen nhưng bạn không chỉ định thời gian; Thử, `/blacklistmode tban <timevalue>`.

Ví dụ về giá trị thời gian: 4 phút = 4 phút, 3 giờ = 3 giờ, 6 ngày = 6 ngày, 5w = 5 tuần."""
                send_message(update.effective_message, teks, parse_mode="markdown")
                return ""
            restime = extract_time(msg, args[1])
            if not restime:
                teks = """Giá trị thời gian không hợp lệ!
Ví dụ về giá trị thời gian: 4 phút = 4 phút, 3 giờ = 3 giờ, 6 ngày = 6 ngày, 5w = 5 tuần."""
                send_message(update.effective_message, teks, parse_mode="markdown")
                return ""
            settypeblacklist = "tạm thời cấm trong {}".format(args[1])
            sql.set_blacklist_strength(chat_id, 6, str(args[1]))
        elif args[0].lower() == "tmute":
            if len(args) == 1:
                teks = """Có vẻ như bạn đã cố gắng đặt giá trị thời gian cho danh sách đen nhưng bạn không chỉ định thời gian; thử, `/blacklistmode tmute <timevalue>`.

Ví dụ về giá trị thời gian: 4 phút = 4 phút, 3 giờ = 3 giờ, 6 ngày = 6 ngày, 5w = 5 tuần."""
                send_message(update.effective_message, teks, parse_mode="markdown")
                return ""
            restime = extract_time(msg, args[1])
            if not restime:
                teks = """Giá trị thời gian không hợp lệ!
Ví dụ về giá trị thời gian: 4 phút = 4 phút, 3 giờ = 3 giờ, 6 ngày = 6 ngày, 5w = 5 tuần."""
                send_message(update.effective_message, teks, parse_mode="markdown")
                return ""
            settypeblacklist = "tạm thời tắt tiếng trong {}".format(args[1])
            sql.set_blacklist_strength(chat_id, 7, str(args[1]))
        else:
            send_message(
                update.effective_message,
                "Vui lòng thêm một tùy chọn: off/del/warn/ban/kick/mute/tban/tmute!",
            )
            return ""
        if conn:
            text = "Đã thay đổi chế độ danh sách đen: `{}` trong *{}*!".format(
                settypeblacklist, chat_name,
            )
        else:
            text = "Changed blacklist mode: `{}`!".format(settypeblacklist)
        send_message(update.effective_message, text, parse_mode="markdown")
        return (
            "<b>{}:</b>\n"
            "<b>Admin:</b> {}\n"
            "Đã thay đổi chế độ danh sách đen. sẽ {}.".format(
                html.escape(chat.title),
                mention_html(user.id, html.escape(user.first_name)),
                settypeblacklist,
            )
        )
    else:
        getmode, getvalue = sql.get_blacklist_setting(chat.id)
        if getmode == 0:
            settypeblacklist = "không làm gì cả"
        elif getmode == 1:
            settypeblacklist = "xóa"
        elif getmode == 2:
            settypeblacklist = "cảnh cáo"
        elif getmode == 3:
            settypeblacklist = "khóa mõm"
        elif getmode == 4:
            settypeblacklist = "kick"
        elif getmode == 5:
            settypeblacklist = "cấm"
        elif getmode == 6:
            settypeblacklist = "tạm bị cấm {}".format(getvalue)
        elif getmode == 7:
            settypeblacklist = "tạm bị khóa mõm {}".format(getvalue)
        if conn:
            text = "Chế độ danh sách đen hiện tại: *{}* trong *{}*.".format(
                settypeblacklist, chat_name,
            )
        else:
            text = "Chế độ danh sách đen hiện tại: *{}*.".format(settypeblacklist)
        send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)
    return ""


def findall(p, s):
    i = s.find(p)
    while i != -1:
        yield i
        i = s.find(p, i + 1)


@run_async
@user_not_admin
def del_blacklist(update, context):
    chat = update.effective_chat
    message = update.effective_message
    user = update.effective_user
    bot = context.bot
    to_match = extract_text(message)
    if not to_match:
        return
    if is_approved(chat.id, user.id):
        return
    getmode, value = sql.get_blacklist_setting(chat.id)

    chat_filters = sql.get_chat_blacklist(chat.id)
    for trigger in chat_filters:
        pattern = r"( |^|[^\w])" + re.escape(trigger) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            try:
                if getmode == 0:
                    return
                elif getmode == 1:
                    try:
                        message.delete()
                    except BadRequest:
                        pass
                elif getmode == 2:
                    try:
                        message.delete()
                    except BadRequest:
                        pass
                    warn(
                        update.effective_user,
                        chat,
                        ("Sử dụng trình kích hoạt trong danh sách đen: {}".format(trigger)),
                        message,
                        update.effective_user,
                    )
                    return
                elif getmode == 3:
                    message.delete()
                    bot.restrict_chat_member(
                        chat.id,
                        update.effective_user.id,
                        permissions=ChatPermissions(can_send_messages=False),
                    )
                    bot.sendMessage(
                        chat.id,
                        f"Khóa mõm {user.first_name} vì đã sử dụng từ khóa cấm!",
                    )
                    return
                elif getmode == 4:
                    message.delete()
                    res = chat.unban_member(update.effective_user.id)
                    if res:
                        bot.sendMessage(
                            chat.id,
                            f"Đã đá {user.first_name} vì phạm luật từ khóa cấm!",
                        )
                    return
                elif getmode == 5:
                    message.delete()
                    chat.kick_member(user.id)
                    bot.sendMessage(
                        chat.id,
                        f"Đã cấm {user.first_name} vì sử dụng từ khóa cấm!",
                    )
                    return
                elif getmode == 6:
                    message.delete()
                    bantime = extract_time(message, value)
                    chat.kick_member(user.id, until_date=bantime)
                    bot.sendMessage(
                        chat.id,
                        f"Tạm thời cấm {user.first_name} trong '{value}' vì chơi ngu!",
                    )
                    return
                elif getmode == 7:
                    message.delete()
                    mutetime = extract_time(message, value)
                    bot.restrict_chat_member(
                        chat.id,
                        user.id,
                        until_date=mutetime,
                        permissions=ChatPermissions(can_send_messages=False),
                    )
                    bot.sendMessage(
                        chat.id,
                        f"Tạm thời khóa mõm {user.first_name} trong '{value}' vì chơi ngu!",
                    )
                    return
            except BadRequest as excp:
                if excp.message != "Không tìm thấy tin nhắn cần xóa":
                    LOGGER.exception("Lỗi khi xóa tin nhắn trong danh sách đen.")
            break


def __import_data__(chat_id, data):
    # set chat blacklist
    blacklist = data.get("blacklist", {})
    for trigger in blacklist:
        sql.add_to_blacklist(chat_id, trigger)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    blacklisted = sql.num_blacklist_chat_filters(chat_id)
    return "Có {} từ khóa trong blacklisted.".format(blacklisted)


def __stats__():
    return "• {} trình kích hoạt danh sách đen, trên {} nhóm.".format(
        sql.num_blacklist_filters(), sql.num_blacklist_filter_chats(),
    )


__mod_name__ = "Danh sách đen"

__help__ = """

Danh sách đen được sử dụng để ngăn một số kích hoạt được nói trong một nhóm. Bất kỳ lúc nào trình kích hoạt được đề cập, thông báo sẽ ngay lập tức bị xóa. Một kết hợp tốt đôi khi là kết hợp điều này với các bộ lọc cảnh báo!

*LƯU Ý*: Danh sách đen không ảnh hưởng đến quản trị viên nhóm.

 • `/blacklist`*:* Xem các từ trong danh sách đen hiện tại.

Admin only:
 • `/addblacklist <triggers>`*:* Thêm một trình kích hoạt vào danh sách đen. Mỗi dòng được coi là một trình kích hoạt, vì vậy việc sử dụng các dòng khác nhau sẽ cho phép bạn thêm nhiều trình kích hoạt.
 • `/unblacklist <triggers>`*:* Xóa các trình kích hoạt khỏi danh sách đen. Logic dòng mới tương tự cũng được áp dụng ở đây, vì vậy bạn có thể loại bỏ nhiều trình kích hoạt cùng một lúc.
 • `/blacklistmode <off/del/warn/ban/kick/mute/tban/tmute>`*:* Hành động thực hiện khi ai đó gửi các từ nằm trong danh sách đen.

Nhãn dán danh sách đen được sử dụng để dừng một số nhãn dán nhất định. Bất cứ khi nào một nhãn dán được gửi đi, tin nhắn sẽ bị xóa ngay lập tức.
*LƯU Ý:* Hình dán danh sách đen không ảnh hưởng đến quản trị viên nhóm
 • `/blsticker`*:* Xem hình dán hiện có trong danh sách đen
*Only admin:*
 • `/addblsticker <sticker link>`*:* Thêm trình kích hoạt nhãn dán vào danh sách đen. Có thể được thêm thông qua hình dán trả lời
 • `/unblsticker <sticker link>`*:* Xóa các trình kích hoạt khỏi danh sách đen. Cùng một logic dòng mới áp dụng ở đây, vì vậy bạn có thể xóa nhiều trình kích hoạt cùng một lúc
 • `/rmblsticker <sticker link>`*:* Giống như trên
 • `/blstickermode <delete/ban/tban/mute/tmute>`*:* thiết lập hành động mặc định về những việc cần làm nếu người dùng sử dụng hình dán trong danh sách đen
Note:
 • `<sticker link>` có thể là `https://t.me/addstickers/<sticker>` hoặc chỉ là `<sticker>` hoặc trả lời tin nhắn nhãn dán

"""
BLACKLIST_HANDLER = DisableAbleCommandHandler(
    "blacklist", blacklist, pass_args=True, admin_ok=True,
)
ADD_BLACKLIST_HANDLER = CommandHandler("addblacklist", add_blacklist)
UNBLACKLIST_HANDLER = CommandHandler("unblacklist", unblacklist)
BLACKLISTMODE_HANDLER = CommandHandler("blacklistmode", blacklist_mode, pass_args=True)
BLACKLIST_DEL_HANDLER = MessageHandler(
    (Filters.text | Filters.command | Filters.sticker | Filters.photo) & Filters.group,
    del_blacklist,
    allow_edit=True,
)

dispatcher.add_handler(BLACKLIST_HANDLER)
dispatcher.add_handler(ADD_BLACKLIST_HANDLER)
dispatcher.add_handler(UNBLACKLIST_HANDLER)
dispatcher.add_handler(BLACKLISTMODE_HANDLER)
dispatcher.add_handler(BLACKLIST_DEL_HANDLER, group=BLACKLIST_GROUP)

__handlers__ = [
    BLACKLIST_HANDLER,
    ADD_BLACKLIST_HANDLER,
    UNBLACKLIST_HANDLER,
    BLACKLISTMODE_HANDLER,
    (BLACKLIST_DEL_HANDLER, BLACKLIST_GROUP),
]

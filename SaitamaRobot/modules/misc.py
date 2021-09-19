from SaitamaRobot.modules.helper_funcs.chat_status import user_admin
from SaitamaRobot.modules.disable import DisableAbleCommandHandler
from SaitamaRobot import dispatcher

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import ParseMode, Update
from telegram.ext.dispatcher import run_async
from telegram.ext import CallbackContext, Filters, CommandHandler

MARKDOWN_HELP = f"""
Markdown là một công cụ định dạng rất mạnh mẽ được hỗ trợ bởi telegram. {dispatcher.bot.first_name} có một số cải tiến, để đảm bảo rằng \
các tin nhắn đã lưu được phân tích cú pháp chính xác và cho phép bạn tạo các nút.

• <code>_italic_</code>: gói văn bản với '_' sẽ tạo ra văn bản in nghiêng
• <code>*bold*</code>: gói văn bản với '*' sẽ tạo ra văn bản in đậm
• <code>`code`</code>: gói văn bản với '`' sẽ tạo ra văn bản monospaced, còn được gọi là 'mã'
• <code>[sometext](someURL)</code>: điều này sẽ tạo ra một liên kết - thông báo sẽ chỉ hiển thị <code>sometext</code>, \
và chạm vào nó sẽ mở ra trang tại <code>someURL</code>.
<b>Example:</b><code>[test](example.com)</code>

• <code>[buttontext](buttonurl:someURL)</code>: đây là một cải tiến đặc biệt để cho phép người dùng có Telegram \
trong phần đánh dấu của họ. <code>buttontext</code> sẽ là những gì được hiển thị trên nút và <code>someurl</code> \
sẽ là url được mở.
<b>Example:</b> <code>[Đây là một nút](nut:example.com)</code>

Nếu bạn muốn nhiều nút trên cùng một dòng, hãy sử dụng :keben, chẳng hạn như:
<code>[one](nut://example.com)
[two](nut://google.com:keben)</code>
Thao tác này sẽ tạo ra hai nút trên một dòng, thay vì một nút trên mỗi dòng.

Hãy nhớ rằng tin nhắn của bạn <b>PHẢI</b> chứa một số văn bản khác ngoài một nút!
"""


@run_async
@user_admin
def echo(update: Update, context: CallbackContext):
    args = update.effective_message.text.split(None, 1)
    message = update.effective_message

    if message.reply_to_message:
        message.reply_to_message.reply_text(
            args[1], parse_mode="MARKDOWN", disable_web_page_preview=True,
        )
    else:
        message.reply_text(
            args[1], quote=False, parse_mode="MARKDOWN", disable_web_page_preview=True,
        )
    message.delete()


def markdown_help_sender(update: Update):
    update.effective_message.reply_text(MARKDOWN_HELP, parse_mode=ParseMode.HTML)
    update.effective_message.reply_text(
        "Hãy thử chuyển tiếp tin nhắn sau cho tôi, bạn sẽ thấy và Sử dụng #test!",
    )
    update.effective_message.reply_text(
        "/save test Đây là một bài kiểm tra đánh dấu. _italics_, *bold*, code, "
        "[URL](example.com) [button](nut:google.com) "
        "[button2](nut://google.com:keben)",
    )


@run_async
def markdown_help(update: Update, context: CallbackContext):
    if update.effective_chat.type != "private":
        update.effective_message.reply_text(
            "Liên hệ với tôi trong pm",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Markdown trợ giúp",
                            url=f"t.me/{context.bot.username}?start=markdownhelp",
                        ),
                    ],
                ],
            ),
        )
        return
    markdown_help_sender(update)


__help__ = """
*Available commands:*
*Markdown:*
 • `/markdownhelp`*:* tóm tắt nhanh về cách hoạt động của markdown trong Telegram - chỉ có thể được gọi trong các cuộc trò chuyện riêng tư
*Paste:*
 • `/paste`*:* Saves replied content to `nekobin.com` and replies with a url
*Bot phát nhạc:*
 • `/play`*:* mở nhạc
"""

ECHO_HANDLER = DisableAbleCommandHandler("echo", echo, filters=Filters.group)
MD_HELP_HANDLER = CommandHandler("markdownhelp", markdown_help)

dispatcher.add_handler(ECHO_HANDLER)
dispatcher.add_handler(MD_HELP_HANDLER)

__mod_name__ = "Bổ sung"
__command_list__ = ["id", "echo"]
__handlers__ = [
    ECHO_HANDLER,
    MD_HELP_HANDLER,
]

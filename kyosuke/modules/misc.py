import contextlib
import html
import time
import git
import requests
from io import BytesIO
from telegram import Chat, Update, MessageEntity, ParseMode, User
from telegram.error import BadRequest
from telegram.ext import Filters, CallbackContext
from telegram.utils.helpers import mention_html, escape_markdown
from subprocess import Popen, PIPE

from kyosuke import (
    dispatcher,
    OWNER_ID,
    SUDO_USERS,
    SUPPORT_USERS,
    DEV_USERS,
    SARDEGNA_USERS,
    WHITELIST_USERS,
    INFOPIC,
    sw,
    StartTime,
)
from kyosuke.__main__ import STATS, USER_INFO, TOKEN
from kyosuke.modules.sql import SESSION
from kyosuke.modules.helper_funcs.chat_status import user_admin, sudo_plus
from kyosuke.modules.helper_funcs.extraction import extract_user
import kyosuke.modules.sql.users_sql as sql
from kyosuke.modules.users import __user_info__ as chat_count
from kyosuke.modules.language import gs
from telegram import __version__ as ptbver, InlineKeyboardMarkup, InlineKeyboardButton
from telethon import __version__ as tlhver
from pyrogram import __version__ as pyrover
from spamwatch import __version__ as __sw__
from pykillerx import __version__ as pykillerx
from psutil import cpu_percent, virtual_memory, disk_usage, boot_time
import datetime
import platform
from platform import python_version
from kyosuke.modules.helper_funcs.decorators import rencmd, rencallback, renmsg

MARKDOWN_HELP = f"""
Markdown is a very powerful formatting tool supported by telegram. {dispatcher.bot.first_name} has some enhancements, to make sure that \
saved messages are correctly parsed, and to allow you to create buttons.

- <code>_italic_</code>: wrapping text with '_' will produce italic text
- <code>*bold*</code>: wrapping text with '*' will produce bold text
- <code>`code`</code>: wrapping text with '`' will produce monospaced text, also known as 'code'
- <code>[sometext](someURL)</code>: this will create a link - the message will just show <code>sometext</code>, \
and tapping on it will open the page at <code>someURL</code>.
EG: <code>[test](example.com)</code>

- <code>[buttontext](buttonurl:someURL)</code>: this is a special enhancement to allow users to have telegram \
buttons in their markdown. <code>buttontext</code> will be what is displayed on the button, and <code>someurl</code> \
will be the url which is opened.
EG: <code>[This is a button](buttonurl:example.com)</code>

If you want multiple buttons on the same line, use :same, as such:
<code>[one](buttonurl://example.com)
[two](buttonurl://google.com:same)</code>
This will create two buttons on a single line, instead of one button per line.

Keep in mind that your message <b>MUST</b> contain some text other than just a button!
"""


@rencmd(command="id", pass_args=True)
def get_id(update: Update, context: CallbackContext):
    bot, args = context.bot, context.args
    message = update.effective_message
    chat = update.effective_chat
    msg = update.effective_message
    if user_id := extract_user(msg, args):
        if msg.reply_to_message and msg.reply_to_message.forward_from:
            user1 = message.reply_to_message.from_user
            user2 = message.reply_to_message.forward_from

            msg.reply_text(
                f"<b>Telegram ID:</b>,"
                f"• {html.escape(user2.first_name)} - <code>{user2.id}</code>.\n"
                f"• {html.escape(user1.first_name)} - <code>{user1.id}</code>.",
                parse_mode=ParseMode.HTML,
            )

        else:
            user = bot.get_chat(user_id)
            new_id = InlineKeyboardMarkup(
                [[InlineKeyboardButton("INFO", url=f"https://t.me/{user.username}")]]
            )
            msg.reply_text(
                f"• {html.escape(user.first_name)}\n"
                f"• Userid by <code>{user.id}</code>",
                parse_mode=ParseMode.HTML,
                reply_markup=new_id,
            )

    elif chat.type == "private":
        msg.reply_text(f"Your id is <code>{chat.id}</code>.", parse_mode=ParseMode.HTML)

    else:
        new_chatinfo = InlineKeyboardMarkup(
            [[InlineKeyboardButton("CHATINFO", url=f"https://t.me/{chat.username}")]]
        )
        msg.reply_text(
            f"• This group's id is <code>{chat.id}</code>.\n",
            parse_mode=ParseMode.HTML,
            reply_markup=new_chatinfo,
        )


@rencmd(command="gifid")
def gifid(update: Update, _):
    msg = update.effective_message
    if msg.reply_to_message and msg.reply_to_message.animation:
        update.effective_message.reply_text(
            f"Gif ID:\n<code>{msg.reply_to_message.animation.file_id}</code>",
            parse_mode=ParseMode.HTML,
        )
    else:
        update.effective_message.reply_text("Please reply to a gif to get its ID.")


@rencmd(command="info", pass_args=True)
def info(update: Update, context: CallbackContext):  # sourcery no-metrics
    bot = context.bot
    args = context.args
    message = update.effective_message
    chat = update.effective_chat
    if user_id := extract_user(update.effective_message, args):
        user = bot.get_chat(user_id)
        new_info = InlineKeyboardMarkup(
            [[InlineKeyboardButton("FBI", url=f"https://t.me/{user.username}")]]
        )

    elif not message.reply_to_message and not args:
        user = (
            message.sender_chat
            if message.sender_chat is not None
            else message.from_user
        )

    elif not message.reply_to_message and (
        not args
        or (
            len(args) >= 1
            and not args[0].startswith("@")
            and not args[0].lstrip("-").isdigit()
            and not message.parse_entities([MessageEntity.TEXT_MENTION])
        )
    ):
        message.reply_text("I can't extract a user from this.")
        return

    else:
        return

    if hasattr(user, "type") and user.type != "private":
        text = get_chat_info(user)
        is_chat = True
    else:
        text = get_user_info(chat, user)
        is_chat = False

    if INFOPIC:
        if is_chat:
            try:
                pic = user.photo.big_file_id
                pfp = bot.get_file(pic).download(out=BytesIO())
                pfp.seek(0)
                message.reply_document(
                    document=pfp,
                    filename=f"{user.id}.jpg",
                    caption=text,
                    parse_mode=ParseMode.HTML,
                )
            except AttributeError:  # AttributeError means no chat pic so just send text
                message.reply_text(
                    text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
        else:
            try:
                profile = bot.get_user_profile_photos(user.id).photos[0][-1]
                _file = bot.get_file(profile["file_id"])

                _file = _file.download(out=BytesIO())
                _file.seek(0)

                message.reply_document(
                    document=_file,
                    caption=(text),
                    parse_mode=ParseMode.HTML,
                )

            # Incase user don't have profile pic, send normal text
            except IndexError:
                message.reply_text(
                    text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=new_info,
                )

    else:
        message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=new_info,
        )


def get_user_info(chat: Chat, user: User) -> str:
    bot = dispatcher.bot
    text = (
        f"<b>General:</b>\n"
        f"ID: <code>{user.id}</code>\n"
        f"First Name: {html.escape(user.first_name)}"
    )
    if user.last_name:
        text += f"\nLast Name: {html.escape(user.last_name)}"
    if user.username:
        text += f"\nUsername: @{html.escape(user.username)}"
    text += f"\nPermanent user link: {mention_html(user.id, 'link')}"
    with contextlib.suppress(Exception):
        if spamwtc := sw.get_ban(int(user.id)):
            text += "<b>\n\nSpamWatch:\n</b>"
            text += "<b>This person is banned in Spamwatch!</b>"
            text += f"\nReason: <pre>{spamwtc.reason}</pre>"
            text += "\nAppeal at @SpamWatchSupport"
        else:
            text += "<b>\n\nSpamWatch:</b>\n Not banned"
    Nation_level_present = False
    num_chats = sql.get_user_num_chats(user.id)
    text += f"\n<b>Chat count</b>: <code>{num_chats}</code>"
    with contextlib.suppress(BadRequest):
        user_member = chat.get_member(user.id)
        if user_member.status == "administrator":
            result = bot.get_chat_member(chat.id, user.id)
            if result.custom_title:
                text += (
                    f"\nThis user holds the title <b>{result.custom_title}</b> here."
                )
    if user.id == OWNER_ID:
        text += "\nThis person is my owner"
        Nation_level_present = True
    elif user.id in DEV_USERS:
        text += "\nThis Person is a part of Eagle Union"
        Nation_level_present = True
    elif user.id in SUDO_USERS:
        text += "\nThe Nation level of this person is Royal"
        Nation_level_present = True
    elif user.id in SUPPORT_USERS:
        text += "\nThe Nation level of this person is Sakura"
        Nation_level_present = True
    elif user.id in SARDEGNA_USERS:
        text += "\nThe Nation level of this person is Sardegna"
        Nation_level_present = True
    elif user.id in WHITELIST_USERS:
        text += "\nThe Nation level of this person is Neptunia"
        Nation_level_present = True
    if Nation_level_present:
        text += f' [<a href="https://t.me/{bot.username}?start=nations">?</a>]'
    text += "\n"
    for mod in USER_INFO:
        if mod.__mod_name__ == "Users":
            continue

        try:
            mod_info = mod.__user_info__(user.id)
        except TypeError:
            mod_info = mod.__user_info__(user.id, chat.id)
        if mod_info:
            text += "\n" + mod_info
    return text


def get_chat_info(user):
    text = f"<b>Chat Info:</b>\n" f"<b>Title:</b> {user.title}"
    if user.username:
        text += f"\n<b>Username:</b> @{html.escape(user.username)}"
    text += f"\n<b>Chat ID:</b> <code>{user.id}</code>"
    text += f"\n<b>Chat Type:</b> {user.type.capitalize()}"
    text += "\n" + chat_count(user.id)

    return text


@rencmd(command="echo", pass_args=True, filters=Filters.chat_type.groups)
@user_admin
def echo(update: Update, _):
    args = update.effective_message.text.split(None, 1)
    message = update.effective_message

    if message.reply_to_message:
        message.reply_to_message.reply_text(args[1])
    else:
        message.reply_text(args[1], quote=False)

    message.delete()


def shell(command):
    process = Popen(command, stdout=PIPE, shell=True, stderr=PIPE)
    stdout, stderr = process.communicate()
    return (stdout, stderr)


@rencmd(command="markdownhelp", filters=Filters.chat_type.private)
def markdown_help(update: Update, _):
    chat = update.effective_chat
    update.effective_message.reply_text(
        (gs(chat.id, "markdown_help_text")), parse_mode=ParseMode.HTML
    )
    update.effective_message.reply_text(
        "Try forwarding the following message to me, and you'll see!"
    )
    update.effective_message.reply_text(
        "/save test This is a markdown test. _italics_, *bold*, `code`, "
        "[URL](example.com) [button](buttonurl:github.com) "
        "[button2](buttonurl://google.com:same)"
    )


def get_readable_time(seconds: int) -> str:
    count = 0
    ping_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]

    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)

    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        ping_time += f"{time_list.pop()}, "

    time_list.reverse()
    ping_time += ":".join(time_list)

    return ping_time


stats_str = """
"""


@rencmd(command="stats", can_disable=False)
@sudo_plus
def stats(update, context):
    db_size = SESSION.execute(
        "SELECT pg_size_pretty(pg_database_size(current_database()))"
    ).scalar_one_or_none()
    uptime = datetime.datetime.fromtimestamp(boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    botuptime = get_readable_time((time.time() - StartTime))
    status = "*╒═══「 System statistics: 」*\n\n"
    status += f"*• System Start time:* {str(uptime)}" + "\n"
    uname = platform.uname()
    status += f"*• System:* {str(uname.system)}" + "\n"
    status += f"*• Release:* {escape_markdown(str(uname.release))}" + "\n"
    status += f"*• Machine:* {escape_markdown(str(uname.machine))}" + "\n"

    mem = virtual_memory()
    cpu = cpu_percent()
    disk = disk_usage("/")
    status += f"*• CPU:* {str(cpu)}" + " %\n"
    status += f"*• RAM:* {str(mem[2])}" + " %\n"
    status += f"*• Storage:* {str(disk[3])}" + " %\n\n"
    status += f"*• Python version:* {python_version()}" + "\n"
    status += f"*• python-telegram-bot:* {str(ptbver)}" + "\n"
    status += f"*• Pyrogram version:* {str(pyrover)}" + "\n"
    status += f"*• Telethon version:* {str(tlhver)}" + "\n"
    status += f"*• Uptime:* {str(botuptime)}" + "\n"
    status += f"*• Database size:* {str(db_size)}" + "\n"
    status += f"*• PyKillerx:* {str(pykillerx)}" + "\n"
    status += f"*• Spamwatch Api:* {str(__sw__)}" + " \n"
    kb = [
        [InlineKeyboardButton("Ping", callback_data="pingCB")],
    ]
    try:
        repo = git.Repo(search_parent_directories=True)
        sha = repo.head.object.hexsha
        status += f"*• Commit*: `{sha[:9]}`\n"
    except Exception as e:
        status += f"*• Commit*: `{str(e)}`\\n"

    try:
        update.effective_message.reply_text(
            status
            + "\n*Bot statistics*:\n"
            + "\n".join([mod.__stats__() for mod in STATS])
            + "\n\n[⍙ GitHub](https://github.com/TeamKillerX/kyosuke) | [⍚ Dev](https://t.me/xtsea/)\n\n"
            + "╘══「 by [Bot](t.me/RendyTapiBot) 」\n",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(kb),
            disable_web_page_preview=True,
        )
    except BaseException:
        update.effective_message.reply_text(
            (
                (
                    (
                        "\n*Bot statistics*:\n"
                        + "\n".join(mod.__stats__() for mod in STATS)
                    )
                    + "\n\n⍙ [GitHub](https://github.com/TeamKillerX/kyosuke) | ⍚ [Dev](https://t.me/xtsea/)\n\n"
                )
                + "╘══「 by [Bot](t.me/RendyTapiBot) 」\n"
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(kb),
            disable_web_page_preview=True,
        )


@rencmd(command="ping")
def ping(update: Update, _):
    new_ping = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Ping", callback_data="pingCB")]]
    )
    msg = update.effective_message
    start_time = time.time()
    message = msg.reply_text("Pinging...")
    end_time = time.time()
    ping_time = round((end_time - start_time) * 1000, 3)
    message.edit_text(
        "*Pong!!!*\n`{}ms`".format(ping_time),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=new_ping,
    )


@rencallback(pattern=r"^pingCB")
def pingCallback(update: Update, context: CallbackContext):
    query = update.callback_query
    start_time = time.time()
    requests.get("https://api.telegram.org")
    end_time = time.time()
    ping_time = round((end_time - start_time) * 1000, 3)
    query.answer(f"Pong! {ping_time}ms")


def get_help(chat):
    return gs(chat, "misc_help")


__mod_name__ = "Misc"

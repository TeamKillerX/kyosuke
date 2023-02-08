import html
import re
from typing import Optional, Union

from telegram import Bot, Chat, ChatMember, Message, Update, ParseMode, User, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import CallbackContext, Filters, CommandHandler, run_async, CallbackQueryHandler
from telegram.utils.helpers import mention_html
from kyosuke.modules.helper_funcs.alternate import typing_action
from kyosuke import (
    DEV_USERS,
    SUDO_USERS,
    SARDEGNA_USERS,
    SUPPORT_USERS,
    OWNER_ID,
    WHITELIST_USERS,
    dispatcher,
)
from kyosuke.modules.helper_funcs.chat_status import (
    user_admin_no_reply,
    bot_admin,
    can_restrict,
    connection_status,
    is_user_admin,
    is_user_ban_protected,
    user_can_ban,
    is_user_in_chat,
)

from kyosuke.modules.helper_funcs.admin_status import user_admin_check, bot_admin_check, AdminPerms

from kyosuke.modules.helper_funcs.extraction import extract_user_and_text
from kyosuke.modules.helper_funcs.string_handling import extract_time
from kyosuke.modules.log_channel import loggable, gloggable
from .helper_funcs.decorators import rencmd, renmsg, rencallback

from ..modules.helper_funcs.anonymous import user_admin, AdminPerms

def ban_user(bot: Bot, who: ChatMember, where_chat_id, reason=None) -> Union[str, bool]:
    try:
        bot.banChatMember(where_chat_id, who.user.id)
    except BadRequest as excp:
        if excp.message != "Reply message not found":
            log.warning("error banning user {}:{} in {} because: {}".format(
                    who.user.first_name, who.user.id, where_chat_id, excp.message))
            return False

    return (
        f"<b>User:</b> <a href=\"tg://user?id={who.user.id}\">{html.escape(who.user.first_name)}</a>"
        f"<b>User ID:</b> {who.user.id}"
        "" if reason is None else f"<b>Reason:</b> {reason}"
    )

def unban_user(bot: Bot, who: ChatMember, where_chat_id, reason=None) -> Union[str, bool]:
    try:
        bot.unbanChatMember(where_chat_id, who.user.id)
    except BadRequest as excp:
        if excp.message != "Reply message not found":
            log.warning("error banning user {}:{} in {} because: {}".format(
                    who.user.first_name, who.user.id, where_chat_id, excp.message))
            return False

    return (
        f"<b>User:</b> <a href=\"tg://user?id={who.user.id}\">{html.escape(who.user.first_name)}</a>"
        f"<b>User ID:</b> {who.user.id}"
        "" if reason is None else f"<b>Reason:</b> {reason}"
    )


@rencmd(command='ban', pass_args=True)
# @renmsg(Filters.regex("(?i)^ban"), group=3)
@connection_status
@bot_admin
@typing_action
@user_admin(AdminPerms.CAN_RESTRICT_MEMBERS)
@loggable
def ban(update: Update, context: CallbackContext) -> Optional[str]:  # sourcery no-metrics
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]
    args = context.args
    bot = context.bot
    log_message = ""
    reason = ""
    if message.reply_to_message and message.reply_to_message.sender_chat:
        r = bot.ban_chat_sender_chat(chat_id=chat.id, sender_chat_id=message.reply_to_message.sender_chat.id)
        if r:
            message.reply_text("Channel {} was banned successfully from {}".format(
                html.escape(message.reply_to_message.sender_chat.title),
                html.escape(chat.title)
            ),
                parse_mode="html"
            )
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"#BANNED\n"
                f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"<b>Channel:</b> {html.escape(message.reply_to_message.sender_chat.title)} ({message.reply_to_message.sender_chat.id})"
            )
        else:
            message.reply_text("Failed to ban channel")
        return

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("I doubt that's a user.")
        return log_message

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message != "User not found":
            raise

        message.reply_text("Can't seem to find this person.")
        return log_message
    if user_id == context.bot.id:
        message.reply_text("Oh yeah, ban myself, noob!")
        return log_message

    if is_user_ban_protected(update, user_id, member) and user not in DEV_USERS:
        if user_id == OWNER_ID:
            message.reply_text("I'd never ban my owner.")
        elif user_id in DEV_USERS:
            message.reply_text("I can't act against our own.")
        elif user_id in SUDO_USERS:
            message.reply_text("My sudos are ban immune")
        elif user_id in SUPPORT_USERS:
            message.reply_text("My support users are ban immune")
        elif user_id in SARDEGNA_USERS:
            message.reply_text("Bring an order from Eagle Union to fight a Sardegna.")
        elif user_id in WHITELIST_USERS:
            message.reply_text("Neptunians are ban immune!")
        else:
            message.reply_text("This user has immunity and cannot be banned.")
        return log_message
    log = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#BANNED\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}\n"
        f"<b>Userid:</b> {member.user.id}"
    )
    if reason:
        log += "\n<b>Reason:</b> {}".format(reason)

    try:
        chat.ban_member(user_id)
        # context.bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        context.bot.sendMessage(
            chat.id,
            "{} was banned by {} in <b>{}</b>\n<b>ID</b>: [<code>{}</code>]\n<b>Reason</b>: {}\n<b>Read</b>: Please take some of your precious time to read the rules!".format(
                mention_html(member.user.id, member.user.first_name), mention_html(user.id, user.first_name),
                message.chat.title, member.user.id, reason
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="How to use ?", callback_data="hacker_help_pub"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                        "📝 Read the rules", url="t.me/{}?start={}".format(dispatcher.bot.username, chat.id)
                        ),
                    ]
                 ]
            ),
            parse_mode=ParseMode.HTML,
        )
        return log

    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            message.reply_text("Banned!", quote=False)
            return log
        else:
            log.warning(update)
            log.exception(
                "ERROR banning user %s in chat %s (%s) due to %s",
                user_id,
                chat.title,
                chat.id,
                excp.message,
            )
            message.reply_text("Well damn, I can't ban that user.")

    return ""


@rencmd(command='tban', pass_args=True)
@connection_status
@bot_admin
@typing_action
@user_admin(AdminPerms.CAN_RESTRICT_MEMBERS)
@loggable
def temp_ban(update: Update, context: CallbackContext) -> str:
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    log_message = ""
    reason = ""
    bot, args = context.bot, context.args

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("I doubt that's a user.")
        return log_message

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message != 'User not found':
            raise
        message.reply_text("I can't seem to find this user.")
        return log_message
    if user_id == bot.id:
        message.reply_text("I'm not gonna BAN myself, are you crazy?")
        return log_message

    if is_user_ban_protected(update, user_id, member):
        message.reply_text("I don't feel like it.")
        return log_message

    if not reason:
        message.reply_text("You haven't specified a time to ban this user for!")
        return log_message

    split_reason = reason.split(None, 1)

    time_val = split_reason[0].lower()
    reason = split_reason[1] if len(split_reason) > 1 else ""
    bantime = extract_time(message, time_val)

    if not bantime:
        return log_message

    log = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        "#TEMP BANNED\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}\n"
        f"<b>Time:</b> {time_val}"
    )
    if reason:
        log += "\n<b>Reason:</b> {}".format(reason)

    try:
        chat.ban_member(user_id, until_date=bantime)
        # bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        bot.sendMessage(
            chat.id,
            f"Banned! User {mention_html(member.user.id, member.user.first_name)} will be banned for {time_val}.\nReason: {reason}",
            parse_mode=ParseMode.HTML,
        )
        return log

    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            message.reply_text(
                f"Banned! User will be banned for {time_val}.", quote=False
            )
            return log
        else:
            log.warning(update)
            log.exception(
                "ERROR banning user %s in chat %s (%s) due to %s",
                user_id,
                chat.title,
                chat.id,
                excp.message,
            )
            message.reply_text("Well damn, I can't ban that user.")

    return log_message


@rencmd(command=['kick', 'kik', 'punch'], pass_args=True)
@connection_status
@bot_admin
@typing_action
@user_admin(AdminPerms.CAN_RESTRICT_MEMBERS)
@loggable
def kick(update: Update, context: CallbackContext) -> str:
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    log_message = ""
    bot, args = context.bot, context.args
    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("I doubt that's a user.")
        return log_message

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message != 'User not found':
            raise
        message.reply_text("I can't seem to find this user.")
        return log_message
    if user_id == bot.id:
        message.reply_text("Yeahhh I'm not gonna do that.")
        return log_message

    if is_user_ban_protected(update, user_id):
        message.reply_text("I really wish I could kick this user....")
        return log_message

    res = chat.unban_member(user_id)  # unban on current user = kick
    if res:
        # bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        bot.sendMessage(
            chat.id,
            f"{mention_html(member.user.id, member.user.first_name)} was kicked by {mention_html(user.id, user.first_name)} in {message.chat.title}\n<b>ID</b>: [<code>{member.user.id}</code>]\n<b>Reason</b>: <code>{reason}</code>",
            parse_mode=ParseMode.HTML,
        )
        log = (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#KICKED\n"
            f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
            f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}"
            f"<b>Userid:</b> {member.user.id}"
        )
        if reason:
            log += f"\n<b>Reason:</b> {reason}"

        return log

    else:
        message.reply_text("Well damn, I can't kick that user.")

    return log_message


@rencmd(command=['kickme' 'kikme', 'kontol', 'memek'], pass_args=True, filters=Filters.chat_type.groups)
@bot_admin
@can_restrict
@typing_action
def kickme(update: Update, context: CallbackContext):
    user_id = update.effective_message.from_user.id
    if is_user_admin(update, user_id):
        update.effective_message.reply_text("I wish I could... but you're an admin.")
        return
    res = update.effective_chat.unban_member(user_id)  # unban on current user = kick
    if res:
        update.effective_message.reply_text("*KICKMEMEK GROUP LEFT*")
    else:
        update.effective_message.reply_text("Huh? I can't :/")


@rencmd(command='unban', pass_args=True)
@connection_status
@bot_admin
@typing_action
@user_admin(AdminPerms.CAN_RESTRICT_MEMBERS)
@loggable
def unban(update: Update, context: CallbackContext) -> Optional[str]:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    log_message = ""
    bot, args = context.bot, context.args
    if message.reply_to_message and message.reply_to_message.sender_chat:
        r = bot.unban_chat_sender_chat(chat_id=chat.id, sender_chat_id=message.reply_to_message.sender_chat.id)
        if r:
            message.reply_text("Channel {} was unbanned successfully from {}".format(
                html.escape(message.reply_to_message.sender_chat.title),
                html.escape(chat.title)
            ),
                parse_mode="html"
            )
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"#UNBANNED\n"
                f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"<b>Channel:</b> {html.escape(message.reply_to_message.sender_chat.title)} ({message.reply_to_message.sender_chat.id})"
            )
        else:
            message.reply_text("Failed to unban channel")
        return
    user_id, reason = extract_user_and_text(message, args)
    if not user_id:
        message.reply_text("I doubt that's a user.")
        return log_message

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message != 'User not found':
            raise
        message.reply_text("I can't seem to find this user.")
        return log_message
    if user_id == bot.id:
        message.reply_text("How would I unban myself if I wasn't here...?")
        return log_message

    if is_user_in_chat(chat, user_id):
        message.reply_text("Isn't this person already here??")
        return log_message

    chat.unban_member(user_id)
    bot.sendMessage(
        chat.id,
        "{} was unbanned by {} in <b>{}</b>\n<b>ID</b>: [<code>{}</code>]\n<b>Reason</b>: <code>{}</code>".format(
            mention_html(member.user.id, member.user.first_name), mention_html(user.id, user.first_name),
            message.chat.title, member.user.id, reason
        ),
        parse_mode=ParseMode.HTML,
    )

    log = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#UNBANNED\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}"
        f"<b>Userid:</b> {member.user.id}"
    )
    if reason:
        log += f"\n<b>Reason:</b> {reason}"

    return log


@rencmd(command='selfunban', pass_args=True)
@connection_status
@bot_admin
@can_restrict
@gloggable
def selfunban(context: CallbackContext, update: Update) -> Optional[str]:
    message = update.effective_message
    user = update.effective_user
    bot, args = context.bot, context.args
    if user.id not in SUDO_USERS or user.id not in SARDEGNA_USERS:
        return

    try:
        chat_id = int(args[0])
    except:
        message.reply_text("Give a valid chat ID.")
        return

    chat = bot.getChat(chat_id)

    try:
        member = chat.get_member(user.id)
    except BadRequest as excp:
        if excp.message == "User not found":
            message.reply_text("I can't seem to find this user.")
            return
        else:
            raise

    if is_user_in_chat(chat, user.id):
        message.reply_text("Aren't you already in the chat??")
        return

    chat.unban_member(user.id)
    message.reply_text("Yep, I have unbanned you.")

    log = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#UNBANNED\n"
        f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}"
    )

    return log

def hacker_pub_help(update: Update, context: CallbackContext):
    update.effective_message.reply_text(
        gs(update.effective_chat.id, "pub_help"),
        parse_mode=ParseMode.HTML,
    )

@rencallback(pattern=r"hacker_help_")
def hacker_help(update: Update, context: CallbackContext):
    query = update.callback_query
    bot = context.bot
    help_info = query.data.split("hacker_help_")[1]
    if help_info == "pub":
        help_text = gs(update.effective_chat.id, "pub_help")
    query.message.edit_text(
        text=help_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text='Report Error', url='https://t.me/pantekyks')
                ]
            ]
        ),
    )
    bot.answer_callback_query(query.id)

from kyosuke.modules.language import gs

__mod_name__ = "Bans"

def get_help(chat):
    return [gs(chat, "bans_help"),
    [
        InlineKeyboardButton(text="Examples", callback_data="hacker_help_pub"
        )
    ]
]

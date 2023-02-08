import html
import re
from typing import Optional, Union

from telegram import Message, Chat, Update, User, ChatPermissions
from telegram.utils.helpers import mention_html
from telegram.ext import Filters, CallbackContext
from telegram.error import BadRequest

from .. import WHITELIST_USERS
from .sql.approve_sql import is_approved
from .helper_funcs.chat_status import connection_status
from .helper_funcs.string_handling import extract_time
from .log_channel import loggable
from .sql import antiflood_sql as sql
from .helper_funcs.alternate import send_message
from .helper_funcs.decorators import rencmd, rencallback, renmsg
from .helper_funcs.admin_status import (
    user_admin_check,
    bot_admin_check,
    AdminPerms,
    user_is_admin
)


FLOOD_GROUP = -5


def mention_html_chat(chat_id: Union[int, str], name: str) -> str:
    return f'<a href="tg://t.me/{chat_id}">{html.escape(name)}</a>'


@renmsg(
        (Filters.all
         & Filters.chat_type.groups
         & ~Filters.status_update
         & ~Filters.update.edited_message
         & ~Filters.sender_chat.channel),
        run_async=True, group=FLOOD_GROUP)

@connection_status
@loggable
def check_flood(update: Update, context: CallbackContext) -> Optional[str]:
    global execstrings
    tag = "None"
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]
    if not user:  # ignore channels
        return ""

    # ignore admins and whitelists
    if user_is_admin(update, user.id, channels = True) or user.id in WHITELIST_USERS:
        sql.update_flood(chat.id, None)
        return ""

    # ignore approved users
    if is_approved(chat.id, user.id):
        sql.update_flood(chat.id, None)
        return

    should_ban = sql.update_flood(chat.id, user.id)
    if not should_ban:
        return ""

    try:
        getmode, getvalue = sql.get_flood_setting(chat.id)
        if getmode == 1:
            chat.ban_member(user.id)
            execstrings = "Banned"
            tag = "BANNED"
        elif getmode == 2:
            chat.ban_member(user.id)
            chat.unban_member(user.id)
            execstrings = "Kicked"
            tag = "KICKED"
        elif getmode == 3:
            context.bot.restrict_chat_member(
                chat.id, user.id, permissions=ChatPermissions(can_send_messages=False)
            )
            execstrings = "Muted"
            tag = "MUTED"
        elif getmode == 4:
            bantime = extract_time(msg, getvalue)
            chat.ban_member(user.id, until_date=bantime)
            execstrings = "Banned for {}".format(getvalue)
            tag = "TBAN"
        elif getmode == 5:
            mutetime = extract_time(msg, getvalue)
            context.bot.restrict_chat_member(
                chat.id,
                user.id,
                until_date=mutetime,
                permissions=ChatPermissions(can_send_messages=False),
            )
            execstrings = "Muted for {}".format(getvalue)
            tag = "TMUTE"
        send_message(
            update.effective_message, "*Anti Flood Triggered!\n{}!".format(execstrings)
        )

        return (
            "<b>{}:</b>"
            "\n#{}"
            "\n<b>User:</b> {}"
            "\nFlooded the group.".format(
                tag, html.escape(chat.title), mention_html(user.id, user.first_name)
            )
        )

    except BadRequest:
        msg.reply_text(
            "I can't restrict people here, give me permissions first! Until then, I'll disable anti-flood."
        )
        sql.set_flood(chat.id, 0)
        return (
            "<b>{}:</b>"
            "\n#INFO"
            "\nDon't have enough permission to restrict users so automatically disabled anti-flood".format(
                chat.title
            )
        )


@renmsg(
        (Filters.all
         & ~Filters.status_update
         & Filters.chat_type.groups
         & ~Filters.update.edited_message
         & Filters.sender_chat.channel),
        run_async=True, group=-6)

@connection_status
@loggable
def check_channel_flood(update: Update, _: CallbackContext) -> Optional[str]:
    global execstrings
    msg = update.effective_message  # type: Optional[Message]
    user = msg.sender_chat  # type: Optional[Chat]
    chat = update.effective_chat  # type: Optional[Chat]
    if not user:  # only for channels
        return ""

    # ignore approved users
    if is_approved(chat.id, user.id):
        sql.update_flood(chat.id, None)
        return

    should_ban = sql.update_flood(chat.id, user.id)
    if not should_ban:
        return ""

    try:
        chat.ban_sender_chat(user.id)
        execstrings = "Banned Channel: " + user.title
        tag = "BANNED"
        send_message(
            update.effective_message, "*Anti Flood Triggered!\n{}!".format(execstrings)
        )

        return (
            "<b>{}:</b>"
            "\n#{}"
            "\n<b>User:</b> {}"
            "\nFlooded the group.".format(
                tag, html.escape(chat.title), mention_html_chat(user.id, user.title)
            )
        )

    except BadRequest:
        msg.reply_text(
            "I can't restrict people here, give me permissions first! Until then, I'll disable anti-flood."
        )
        sql.set_flood(chat.id, 0)
        return (
            "<b>{}:</b>"
            "\n#INFO"
            "\nDon't have enough permission to restrict users so automatically disabled anti-flood".format(
                chat.title
            )
        )


@rencallback(pattern=r"unmute_flooder")
@bot_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS)
@user_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS, allow_mods = True, noreply = True)
@loggable
def flood_button(update: Update, context: CallbackContext) -> str:
    bot = context.bot
    query = update.callback_query
    user = update.effective_user
    chat = update.effective_chat
    admeme = chat.get_member(user.id)
    match = re.match(r"unmute_flooder\((.+?)\)", query.data)

    if match:
        user_id = match.group(1)
        chat = update.effective_chat.id
        try:
            bot.restrict_chat_member(
                chat,
                int(user_id),
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
            update.effective_message.edit_text(
                f"Unmuted{f' by {mention_html(user.id, user.first_name)}' if not admeme.is_anonymous else ''}.",
                parse_mode="HTML",
            )
            logmsg = (
                    f"<b>{html.escape(chat.title)}:</b>\n"
                    f"#UNMUTE_FLOODER\n"
                    f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
                    f"<b>User:</b> {mention_html(user_id, html.escape(chat.get_member(user_id).first_name))}\n"
            )
            return logmsg
        except Exception as e:
            update.effective_message.edit_text("An error occurred while unmuting!\n<code>{}</code>".format(e))


@rencmd(command='setflood', pass_args=True)
@connection_status
@bot_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS)
@user_admin_check(AdminPerms.CAN_CHANGE_INFO, allow_mods = True)
@loggable
def set_flood(update, context) -> Optional[str]:  # sourcery no-metrics
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    args = context.args; print(args)
    user = update.effective_user  # type: Optional[User]
    chat_name = chat.title

    if len(args) >= 1:
        val = args[0].lower()
        if val in ["off", "no", "0"]:
            sql.set_flood(chat.id, 0)
            message.reply_text("Antiflood has been disabled.")

        elif val.isdigit():
            amount = int(val)
            if amount <= 0:
                sql.set_flood(chat.id, 0)
                message.reply_text("Antiflood has been disabled.")
                return (
                    "<b>{}:</b>"
                    "\n#SETFLOOD"
                    "\n<b>Admin:</b> {}"
                    "\nDisable antiflood.".format(
                        html.escape(chat_name), mention_html(user.id, user.first_name)
                    )
                )

            elif amount <= 3:
                send_message(
                    update.effective_message,
                    "Antiflood must be either 0 (disabled) or number greater than 3!",
                )
                return ""

            else:
                sql.set_flood(chat.id, amount)
                message.reply_text("Successfully updated anti-flood limit to {}!".format(amount))
                return (
                    "<b>{}:</b>"
                    "\n#SETFLOOD"
                    "\n<b>Admin:</b> {}"
                    "\nSet antiflood to <code>{}</code>.".format(
                        html.escape(chat_name),
                        mention_html(user.id, user.first_name),
                        amount,
                    )
                )

        else:
            message.reply_text("Invalid argument please use a number, 'off' or 'no'")
    else:
        message.reply_text(
                "Use `/setflood number` to enable anti-flood.\nOr use `/setflood off` to disable antiflood!",
            parse_mode="markdown",
        )
    return ""


@rencmd(command="flood")
@connection_status
@bot_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS)
@user_admin_check()
def flood(update: Update, _: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message

    limit = sql.get_flood_limit(chat.id)
    flood_type = get_flood_type(chat.id)
    if limit == 0:
        msg.reply_text("I'm not enforcing any flood control here!")

    else:
        msg.reply_text(
            "I'm currently restricting members after {} consecutive messages.\nThe current flood mode is:\n  {}".format(
                limit, flood_type
            )
        )


@rencmd(command=["setfloodmode", "floodmode"], pass_args=True)
@bot_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS)
@user_admin_check(AdminPerms.CAN_CHANGE_INFO, allow_mods = True)
@connection_status
@loggable
def set_flood_mode(update, context) -> Optional[str]:  # sourcery no-metrics
    global settypeflood
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat
    msg = update.effective_message

    if args := context.args:
        if args[0].lower() == "ban":
            settypeflood = "ban"
            sql.set_flood_strength(chat.id, 1, "0")
        elif args[0].lower() == "kick":
            settypeflood = "kick"
            sql.set_flood_strength(chat.id, 2, "0")
        elif args[0].lower() == "mute":
            settypeflood = "mute"
            sql.set_flood_strength(chat.id, 3, "0")
        elif args[0].lower() == "tban":
            if len(args) == 1:
                send_message(update.effective_message, tflood_help_msg.format("tban"), parse_mode="markdown")
                return
            settypeflood = "tban for {}".format(args[1])
            sql.set_flood_strength(chat.id, 4, str(args[1]))
        elif args[0].lower() == "tmute":
            if len(args) == 1:
                send_message(update.effective_message, tflood_help_msg.format("tmute"), parse_mode="markdown")
                return
            settypeflood = "tmute for {}".format(args[1])
            sql.set_flood_strength(chat.id, 5, str(args[1]))
        else:
            send_message(
                update.effective_message, "I only understand ban/kick/mute/tban/tmute!"
            )
            return
        msg.reply_text(
                "Exceeding consecutive flood limit will result in {}!".format(settypeflood)
            )
        return (
            "<b>{}:</b>\n"
            "#FLOODMODE\n"
            "<b>Admin:</b> {}\n"
            "New Flood Mode: {}.".format(
                html.escape(chat.title),
                mention_html(user.id, user.first_name),
                settypeflood,
            )
        )
    else:
        flood_type = get_flood_type(chat.id)

        msg.reply_text("Sending more message than flood limit will result in {}.".format(flood_type))

    return ""


def get_flood_type(chat_id: int) -> str:
    global settypeflood
    getmode, getvalue = sql.get_flood_setting(chat_id)
    if getmode == 1:
        settypeflood = "ban"
    elif getmode == 2:
        settypeflood = "kick"
    elif getmode == 3:
        settypeflood = "mute"
    elif getmode == 4:
        settypeflood = "tban for {}".format(getvalue)
    elif getmode == 5:
        settypeflood = "tmute for {}".format(getvalue)
    return settypeflood


tflood_help_msg = ("It looks like you tried to set time value for antiflood but you didn't specified time; "
                   "Try, `/setfloodmode {} <timevalue>`."
                   "Examples of time value: 4m = 4 minutes, 3h = 3 hours, 6d = 6 days, 5w = 5 weeks.")


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    limit = sql.get_flood_limit(chat_id)
    if limit == 0:
        return "Not enforcing to flood control."
    else:
        return "Antiflood has been set to`{}`.".format(limit)


from .language import gs


def get_help(chat):
    return gs(chat, "antiflood_help")


__mod_name__ = "Anti-Flood"

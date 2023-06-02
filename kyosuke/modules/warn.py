import html
import re
from typing import Optional
from sqlalchemy.sql.expression import false

import telegram
from kyosuke import (
    BAN_STICKER,
    DEV_USERS,
    OWNER_ID,
    SUDO_USERS,
    WHITELIST_USERS,
    dispatcher,
)

from .helper_funcs.extraction import (
    extract_text,
    extract_user,
    extract_user_and_text,
)
from .helper_funcs.filters import CustomFilters
from .helper_funcs.misc import split_message
from .helper_funcs.string_handling import split_quotes
from .log_channel import loggable
from .sql import warns_sql as sql
from .sql.approve_sql import is_approved
from telegram import (
    CallbackQuery,
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ParseMode,
    Update,
    User,
)
from telegram.error import BadRequest
from telegram.ext import (
    CallbackContext,
    DispatcherHandlerStop,
    Filters,
)
from telegram.utils.helpers import mention_html
from .helper_funcs.decorators import rencmd, renmsg, rencallback

from .helper_funcs.admin_status import (
    user_admin_check,
    bot_admin_check,
    AdminPerms,
    get_bot_member,
    bot_is_admin,
    user_is_admin,
    user_not_admin_check,
)

WARN_HANDLER_GROUP = 9
CURRENT_WARNING_FILTER_STRING = "<b>Current warning filters in this chat:</b>\n"
WARNS_GROUP = 3


def warn_immune(message, update, uid, warner):
    if user_is_admin(update, uid):
        if uid is OWNER_ID:
            message.reply_text("This is my CREATOR, how dare you!")
            return True
        if uid in DEV_USERS:
            message.reply_text("This user is one of my Devs, go cry somewhere else.")
            return True
        if uid in SUDO_USERS:
            message.reply_text("This user is a SUDO user, i'm not gonna warn him!")
        else:
            message.reply_text("Damn admins, They are too far to be warned!")
        return True
    if uid not in WHITELIST_USERS:
        return False
    if warner:
        message.reply_text("Whitelisted users are warn immune.")
    else:
        message.reply_text(
            "A whitelisted user triggered an auto warn filter!\nI can't warn them users but they should avoid abusing this."
        )
    return True


# Not async
def warn(
    user: User, update: Update, reason: str, message: Message, warner: User = None
) -> Optional[str]:  # sourcery no-metrics
    chat = update.effective_chat
    if warn_immune(message=message, update=update, uid=user.id, warner=warner):
        return

    if warner:
        warner_tag = mention_html(warner.id, warner.first_name)
    else:
        warner_tag = "Automated warn filter."

    limit, soft_warn = sql.get_warn_setting(chat.id)
    num_warns, reasons = sql.warn_user(user.id, chat.id, reason)
    if num_warns >= limit:
        sql.reset_warns(user.id, chat.id)
        if soft_warn:  # kick
            chat.unban_member(user.id)
            reply = (
                f"<code>❕</code><b>Kick Event</b>\n"
                f"<code> </code><b>•  User:</b> {mention_html(user.id, user.first_name)}\n"
                f"<code> </code><b>•  Count:</b> {limit}\n"
                f"<code> </code><b>•  Id:</b> {user.id}"
            )

        else:  # ban
            chat.ban_member(user.id)
            reply = (
                f"<code>❕</code><b>Ban Event</b>\n"
                f"<code> </code><b>•  User:</b> {mention_html(user.id, user.first_name)}\n"
                f"<code> </code><b>•  Count:</b> {limit}\n"
                f"<code> </code><b>•  Id:</b> {user.id}"
            )

        for warn_reason in reasons:
            reply += f"\n - {html.escape(warn_reason)}"

        keyboard = None
        log_reason = (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#WARN_BAN\n"
            f"<b>Admin:</b> {warner_tag}\n"
            f"<b>User:</b> {mention_html(user.id, user.first_name)}\n"
            f"<b>User ID:</b> <code>{user.id}</code>\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Counts:</b> <code>{num_warns}/{limit}</code>"
        )

    else:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔘 Remove warn", callback_data=f"rm_warn({user.id})"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📝 Read the rules",
                        url=f"t.me/{dispatcher.bot.username}?start={chat.id}",
                    )
                ],
            ]
        )

        reply = (
            f"<code>❕</code><b>Warn Event</b>\n"
            f"<code> </code><b>•  User:</b> {mention_html(user.id, user.first_name)}\n"
            f"<code> </code><b>•  Count:</b> {num_warns}/{limit}\n"
            f"<code> </code><b>•  Id:</b> {user.id}\n"
        )
        if reason:
            reply += f"\n<code> </code><b>•  Reason:</b> {html.escape(reason)}"
        reply += "\nPlease take some of your precious time to read the rules!"

        log_reason = (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#WARN\n"
            f"<b>Admin:</b> {warner_tag}\n"
            f"<b>User:</b> {mention_html(user.id, user.first_name)}\n"
            f"<b>User ID:</b> <code>{user.id}</code>\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Counts:</b> <code>{num_warns}/{limit}</code>"
        )

    try:
        message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            message.reply_text(
                reply, reply_markup=keyboard, parse_mode=ParseMode.HTML, quote=False
            )
        else:
            raise
    return log_reason


# Not async
def swarn(
    user: User,
    update: Update,
    reason: str,
    message: Message,
    dels,
    warner: User = None,
) -> str:  # sourcery no-metrics
    if warn_immune(message=message, update=update, uid=user.id, warner=warner):
        return
    chat = update.effective_chat

    if warner:
        warner_tag = mention_html(warner.id, warner.first_name)
    else:
        warner_tag = "Automated warn filter."

    limit, soft_warn = sql.get_warn_setting(chat.id)
    num_warns, reasons = sql.warn_user(user.id, chat.id, reason)
    if num_warns >= limit:
        sql.reset_warns(user.id, chat.id)
        if soft_warn:  # kick
            chat.unban_member(user.id)
            reply = (
                f"<code>❕</code><b>Kick Event</b>\n"
                f"<code> </code><b>•  User:</b> {mention_html(user.id, user.first_name)}\n"
                f"<code> </code><b>•  Count:</b> {limit}\n"
                f"<code> </code><b>•  Id:</b> {user.id}"
            )

        else:  # ban
            chat.ban_member(user.id)
            reply = (
                f"<code>❕</code><b>Ban Event</b>\n"
                f"<code> </code><b>•  User:</b> {mention_html(user.id, user.first_name)}\n"
                f"<code> </code><b>•  Count:</b> {limit}\n"
                f"<code> </code><b>•  Id:</b> {user.id}"
            )

        for warn_reason in reasons:
            reply += f"\n - {html.escape(warn_reason)}"

        keyboard = None
        log_reason = (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#WARN_BAN\n"
            f"<b>Admin:</b> {warner_tag}\n"
            f"<b>User:</b> {mention_html(user.id, user.first_name)}\n"
            f"<b>User ID:</b> <code>{user.id}</code>\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Counts:</b> <code>{num_warns}/{limit}</code>"
        )

    else:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔘 Remove warn", callback_data=f"rm_warn({user.id})"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📝 Read the rules",
                        url=f"t.me/{dispatcher.bot.username}?start={chat.id}",
                    )
                ],
            ]
        )

        reply = (
            f"<code>❕</code><b>Warn Event</b>\n"
            f"<code> </code><b>•  User:</b> {mention_html(user.id, user.first_name)}\n"
            f"<code> </code><b>•  Count:</b> {num_warns}/{limit}\n"
            f"<code> </code><b>•  Id:</b> {user.id}"
        )
        if reason:
            reply += f"\n<code> </code><b>•  Reason:</b> {html.escape(reason)}"

        reply += f"\nPlease take some of your precious time to read the rules!"

        log_reason = (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#WARN\n"
            f"<b>Admin:</b> {warner_tag}\n"
            f"<b>User:</b> {mention_html(user.id, user.first_name)}\n"
            f"<b>User ID:</b> <code>{user.id}</code>\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Counts:</b> <code>{num_warns}/{limit}</code>"
        )

    try:
        if dels:
            if message.reply_to_message:
                message.reply_to_message.delete()
        message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        message.delete()
    except BadRequest as excp:
        if excp.message != "Reply message not found":
            raise
        # Do not reply
        if message.reply_to_message:
            message.reply_to_message.delete()
        message.reply_text(
            reply, reply_markup=keyboard, parse_mode=ParseMode.HTML, quote=False
        )
        message.delete()
    return log_reason


# Not async
def dwarn(
    user: User, update: Update, reason: str, message: Message, warner: User = None
) -> str:  # sourcery no-metrics
    if warn_immune(message=message, update=update, uid=user.id, warner=warner):
        return
    chat = update.effective_chat
    if warner:
        warner_tag = mention_html(warner.id, warner.first_name)
    else:
        warner_tag = "Automated warn filter."

    limit, soft_warn = sql.get_warn_setting(chat.id)
    num_warns, reasons = sql.warn_user(user.id, chat.id, reason)
    if num_warns >= limit:
        sql.reset_warns(user.id, chat.id)
        if soft_warn:  # kick
            chat.unban_member(user.id)
            reply = (
                f"<code>❕</code><b>Kick Event</b>\n"
                f"<code> </code><b>•  User:</b> {mention_html(user.id, user.first_name)}\n"
                f"<code> </code><b>•  Count:</b> {limit}\n"
                f"<code> </code><b>•  Id:</b> {user.id}"
            )

        else:  # ban
            chat.ban_member(user.id)
            reply = (
                f"<code>❕</code><b>Ban Event</b>\n"
                f"<code> </code><b>•  User:</b> {mention_html(user.id, user.first_name)}\n"
                f"<code> </code><b>•  Count:</b> {limit}\n"
                f"<code> </code><b>•  Id:</b> {user.id}"
            )

        for warn_reason in reasons:
            reply += f"\n - {html.escape(warn_reason)}"

        keyboard = None
        log_reason = (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#WARN_BAN\n"
            f"<b>Admin:</b> {warner_tag}\n"
            f"<b>User:</b> {mention_html(user.id, user.first_name)}\n"
            f"<b>User ID:</b> <code>{user.id}</code>\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Counts:</b> <code>{num_warns}/{limit}</code>"
        )

    else:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔘 Remove warn", callback_data=f"rm_warn({user.id})"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📝 Read the rules",
                        url=f"t.me/{dispatcher.bot.username}?start={chat.id}",
                    )
                ],
            ]
        )

        reply = (
            f"<code>❕</code><b>Warn Event</b>\n"
            f"<code> </code><b>•  User:</b> {mention_html(user.id, user.first_name)}\n"
            f"<code> </code><b>•  Count:</b> {num_warns}/{limit}\n"
            f"<code> </code><b>•  Id:</b> {user.id}"
        )
        if reason:
            reply += f"\n<code> </code><b>•  Reason:</b> {html.escape(reason)}"
        reply += f"\nPlease take some of your precious time to read the rules!"

        log_reason = (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#WARN\n"
            f"<b>Admin:</b> {warner_tag}\n"
            f"<b>User:</b> {mention_html(user.id, user.first_name)}\n"
            f"<b>User ID:</b> <code>{user.id}</code>\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Counts:</b> <code>{num_warns}/{limit}</code>"
        )

    try:
        if message.reply_to_message:
            message.reply_to_message.delete()
        message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except BadRequest as excp:
        if excp.message != "Reply message not found":
            raise
        # Do not reply
        if message.reply_to_message:
            message.reply_to_message.delete()
        message.reply_text(
            reply, reply_markup=keyboard, parse_mode=ParseMode.HTML, quote=False
        )
    return log_reason


@rencallback(pattern=r"rm_warn")
@bot_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS)
@user_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS, noreply=True)
@loggable
def button(update: Update, _: CallbackContext) -> str:
    query: Optional[CallbackQuery] = update.callback_query
    user: Optional[User] = update.effective_user
    if match := re.match(r"rm_warn\((.+?)\)", query.data):
        user_id = match[1]
        chat: Optional[Chat] = update.effective_chat
        if sql.remove_warn(user_id, chat.id):
            update.effective_message.edit_text(
                "Warn removed by {}.".format(
                    mention_html(user.id, user.first_name)
                    if not user_is_admin(update, user.id, perm=AdminPerms.IS_ANONYMOUS)
                    else "anon admin"
                ),
                parse_mode=ParseMode.HTML,
            )
            user_member = chat.get_member(user_id)
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"#UNWARN\n"
                f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"<b>User:</b> {mention_html(user_member.user.id, user_member.user.first_name)}\n"
                f"<b>User ID:</b> <code>{user_member.user.id}</code>"
            )
        else:
            update.effective_message.edit_text(
                "User already has no warns.", parse_mode=ParseMode.HTML
            )

    return ""


@rencmd(command=["warn", "dwarn", "delwarn", "dswarn", "dswarn"], pass_args=True)
@bot_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS)
@user_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS, allow_mods=True)
@loggable
def warn_user(update: Update, context: CallbackContext) -> str:
    args = context.args
    message: Optional[Message] = update.effective_message
    chat: Optional[Chat] = update.effective_chat
    warner: Optional[User] = update.effective_user
    user_id, reason = extract_user_and_text(message, args)

    if (
        message.reply_to_message and message.reply_to_message.sender_chat
    ) or user_id < 0:
        message.reply_text(
            "This command can't be used on channels, however you can ban them instead."
        )
        return ""

    if message.text.startswith(("/s", "!s")):
        silent = True
        if not bot_is_admin(chat, AdminPerms.CAN_DELETE_MESSAGES):
            return ""
    else:
        silent = False
    if message.text.startswith(("/d", "!d")):
        delban = True
        if not bot_is_admin(chat, AdminPerms.CAN_DELETE_MESSAGES):
            return ""
    else:
        delban = False
    if message.text.startswith(("/ds", "!ds")):
        delsilent = True
        if not bot_is_admin(chat, AdminPerms.CAN_DELETE_MESSAGES):
            return ""
    else:
        delsilent = False
    if silent:
        dels = False
        if user_id:
            if (
                message.reply_to_message
                and message.reply_to_message.from_user.id == user_id
            ):
                return swarn(
                    message.reply_to_message.from_user,
                    update,
                    reason,
                    message,
                    dels,
                    warner,
                )
            else:
                return swarn(
                    chat.get_member(user_id).user, update, reason, message, dels, warner
                )
        else:
            message.reply_text("That looks like an invalid User ID to me.")
    if not delsilent and delban and user_id:
        return (
            dwarn(
                message.reply_to_message.from_user,
                update,
                reason,
                message,
                warner,
            )
            if (
                message.reply_to_message
                and message.reply_to_message.from_user.id == user_id
            )
            else dwarn(chat.get_member(user_id).user, update, reason, message, warner)
        )
    elif not delsilent and delban or not delsilent and not user_id:
        message.reply_text("That looks like an invalid User ID to me.")
    elif delsilent:
        dels = True
        if user_id:
            if (
                message.reply_to_message
                and message.reply_to_message.from_user.id == user_id
            ):
                return swarn(
                    message.reply_to_message.from_user,
                    update,
                    reason,
                    message,
                    dels,
                    warner,
                )
            else:
                return swarn(
                    chat.get_member(user_id).user, update, reason, message, dels, warner
                )
        else:
            message.reply_text("That looks like an invalid User ID to me.")
    else:
        return (
            warn(
                message.reply_to_message.from_user,
                update,
                reason,
                message.reply_to_message,
                warner,
            )
            if (
                message.reply_to_message
                and message.reply_to_message.from_user.id == user_id
            )
            else warn(chat.get_member(user_id).user, update, reason, message, warner)
        )
    return ""


@rencmd(command=["resetwarn", "resetwarns"], pass_args=True)
@bot_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS)
@user_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS)
@loggable
def reset_warns(update: Update, context: CallbackContext) -> str:
    args = context.args
    message: Optional[Message] = update.effective_message
    chat: Optional[Chat] = update.effective_chat
    user: Optional[User] = update.effective_user

    if user_id := extract_user(message, args):
        sql.reset_warns(user_id, chat.id)
        message.reply_text("Warns have been reset!")
        warned = chat.get_member(user_id).user
        return (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#RESETWARNS\n"
            f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
            f"<b>User:</b> {mention_html(warned.id, warned.first_name)}\n"
            f"<b>User ID:</b> <code>{warned.id}</code>"
        )
    else:
        message.reply_text("No user has been designated!")
    return ""


@rencmd(command="warns", pass_args=True, can_disable=True)
def warns(update: Update, context: CallbackContext):
    args = context.args
    message: Optional[Message] = update.effective_message
    chat: Optional[Chat] = update.effective_chat
    user_id = extract_user(message, args) or update.effective_user.id
    result = sql.get_warns(user_id, chat.id)

    if result and result[0] != 0:
        num_warns, reasons = result
        limit, soft_warn = sql.get_warn_setting(chat.id)

        if reasons:
            text = (
                f"This user has {num_warns}/{limit} warns, for the following reasons:"
            )
            for reason in reasons:
                text += f"\n • {reason}"

            msgs = split_message(text)
            for msg in msgs:
                update.effective_message.reply_text(msg)
        else:
            update.effective_message.reply_text(
                f"User has {num_warns}/{limit} warns, but no reasons for any of them."
            )
    else:
        update.effective_message.reply_text("This user doesn't have any warns!")


@rencmd(command="addwarn", pass_args=True, run_async=False)
@bot_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS)
# Dispatcher handler stop - do not async
@user_admin_check(AdminPerms.CAN_CHANGE_INFO, allow_mods=True)
def add_warn_filter(update: Update, context: CallbackContext):
    chat: Optional[Chat] = update.effective_chat
    msg: Optional[Message] = update.effective_message
    user = update.effective_user

    args = msg.text.split(
        None, 1
    )  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) < 2:
        return

    # set trigger -> lower, so as to avoid adding duplicate filters with different cases
    keyword = extracted[0].lower()
    content = extracted[1]

    # Note: perhaps handlers can be removed somehow using sql.get_chat_filters
    for handler in dispatcher.handlers.get(WARN_HANDLER_GROUP, []):
        if handler.filters == (keyword, chat.id):
            dispatcher.remove_handler(handler, WARN_HANDLER_GROUP)

    sql.add_warn_filter(chat.id, keyword, content)

    update.effective_message.reply_text(f"Warn handler added for '{keyword}'!")
    raise DispatcherHandlerStop


@rencmd(command=["nowarn", "stopwarn"], pass_args=True)
@bot_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS)
@user_admin_check(AdminPerms.CAN_CHANGE_INFO)
def remove_warn_filter(update: Update, context: CallbackContext):
    chat: Optional[Chat] = update.effective_chat
    msg: Optional[Message] = update.effective_message
    user = update.effective_user

    args = msg.text.split(
        None, 1
    )  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) < 1:
        return

    to_remove = extracted[0]

    chat_filters = sql.get_chat_warn_triggers(chat.id)

    if not chat_filters:
        msg.reply_text("No warning filters are active here!")
        return

    for filt in chat_filters:
        if filt == to_remove:
            sql.remove_warn_filter(chat.id, to_remove)
            msg.reply_text("Okay, I'll stop warning people for that.")
            raise DispatcherHandlerStop

    msg.reply_text(
        "That's not a current warning filter - run /warnlist for all active warning filters."
    )


@rencmd(command=["warnlist", "warnfilters"], pass_args=True)
def list_warn_filters(update: Update, context: CallbackContext):
    chat: Optional[Chat] = update.effective_chat
    all_handlers = sql.get_chat_warn_triggers(chat.id)

    if not all_handlers:
        update.effective_message.reply_text("No warning filters are active here!")
        return

    filter_list = CURRENT_WARNING_FILTER_STRING
    for keyword in all_handlers:
        entry = f" - {html.escape(keyword)}\n"
        if len(entry) + len(filter_list) > telegram.MAX_MESSAGE_LENGTH:
            update.effective_message.reply_text(filter_list, parse_mode=ParseMode.HTML)
            filter_list = entry
        else:
            filter_list += entry

    if filter_list != CURRENT_WARNING_FILTER_STRING:
        update.effective_message.reply_text(filter_list, parse_mode=ParseMode.HTML)


@renmsg((CustomFilters.has_text & Filters.chat_type.groups), group=WARNS_GROUP)
@loggable
def reply_filter(update: Update, context: CallbackContext) -> Optional[str]:
    chat: Optional[Chat] = update.effective_chat
    message: Optional[Message] = update.effective_message
    user: Optional[User] = update.effective_user

    if not user:  # Ignore channel
        return

    if user.id == 777000:
        return
    if is_approved(chat.id, user.id):
        return

    chat_warn_filters = sql.get_chat_warn_triggers(chat.id)
    to_match = extract_text(message)
    if not to_match:
        return ""

    for keyword in chat_warn_filters:
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            user: Optional[User] = update.effective_user
            warn_filter = sql.get_warn_filter(chat.id, keyword)
            return warn(user, update, warn_filter.reply, message)
    return ""


@rencmd(command="warnlimit", pass_args=True)
@user_admin_check(AdminPerms.CAN_CHANGE_INFO)
@loggable
def set_warn_limit(update: Update, context: CallbackContext) -> str:
    chat: Optional[Chat] = update.effective_chat
    msg: Optional[Message] = update.effective_message
    if args := context.args:
        user = update.effective_user
        if args[0].isdigit():
            if int(args[0]) < 3:
                msg.reply_text("The minimum warn limit is 3!")
            else:
                sql.set_warn_limit(chat.id, int(args[0]))
                msg.reply_text(f"Updated the warn limit to {args[0]}")
                return (
                    f"<b>{html.escape(chat.title)}:</b>\n"
                    f"#SET_WARN_LIMIT\n"
                    f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
                    f"Set the warn limit to <code>{args[0]}</code>"
                )
        else:
            msg.reply_text("Give me a number as an arg!")
    else:
        limit, _ = sql.get_warn_setting(chat.id)

        msg.reply_text(f"The current warn limit is {limit}")
    return ""


@rencmd(command="strongwarn", pass_args=True)
@user_admin_check(AdminPerms.CAN_CHANGE_INFO)
def set_warn_strength(update: Update, context: CallbackContext):
    chat: Optional[Chat] = update.effective_chat
    msg: Optional[Message] = update.effective_message

    if args := context.args:
        user: Optional[User] = update.effective_user
        if args[0].lower() in ("on", "yes"):
            sql.set_warn_strength(chat.id, False)
            msg.reply_text("Too many warns will now result in a Ban!")
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"Has enabled strong warns. Users will be banned"
            )

        elif args[0].lower() in ("off", "no"):
            sql.set_warn_strength(chat.id, True)
            msg.reply_text(
                "Too many warns will now result in a kick! Users will be able to join again after."
            )
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"Has disabled bans. I will just kick users."
            )

        else:
            msg.reply_text("I only understand on/yes/no/off!")
    else:
        limit, soft_warn = sql.get_warn_setting(chat.id)
        if soft_warn:
            msg.reply_text(
                "Warns are currently set to *kick* users when they exceed the limits.",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            msg.reply_text(
                "Warns are currently set to *Ban* users when they exceed the limits.",
                parse_mode=ParseMode.MARKDOWN,
            )
    return ""


def __stats__():
    return (
        f"• {sql.num_warns()} overall warns, across {sql.num_warn_chats()} chats.\n"
        f"• {sql.num_warn_filters()} warn filters, across {sql.num_warn_filter_chats()} chats."
    )


def __import_data__(chat_id, data):
    for user_id, count in data.get("warns", {}).items():
        for _ in range(int(count)):
            sql.warn_user(user_id, chat_id)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    num_warn_filters = sql.num_warn_chat_filters(chat_id)
    limit, soft_warn = sql.get_warn_setting(chat_id)
    return (
        f"This chat has `{num_warn_filters}` warn filters. "
        f"It takes `{limit}` warns before the user gets *{'kicked' if soft_warn else 'banned'}*."
    )


from .language import gs


def get_help(chat):
    return gs(chat, "warns_help")


__mod_name__ = "Warnings"

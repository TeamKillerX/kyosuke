import html
import ast
from telegram import Message, Chat, ParseMode, MessageEntity, message
from telegram import TelegramError, ChatPermissions
from telegram.error import BadRequest
from telegram.ext import Filters
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.utils.helpers import mention_html
from .helper_funcs.chat_status import connection_status
from .helper_funcs.decorators import rencmd, renmsg
from alphabet_detector import AlphabetDetector
from .sql.approve_sql import is_approved
import kyosuke.modules.sql.locks_sql as sql
from kyosuke import dispatcher, SUDO_USERS, log

from .log_channel import loggable

from .helper_funcs.alternate import send_message, typing_action

from .helper_funcs.admin_status import (
    user_admin_check,
    bot_admin_check,
    AdminPerms,
    get_bot_member,
    bot_is_admin,
    user_is_admin,
    user_not_admin_check,
)

ad = AlphabetDetector()

LOCK_TYPES = {
    "audio": Filters.audio,
    "voice": Filters.voice,
    "document": Filters.document,
    "video": Filters.video,
    "contact": Filters.contact,
    "photo": Filters.photo,
    "url": Filters.entity(MessageEntity.URL)
    | Filters.caption_entity(MessageEntity.URL),
    "bots": Filters.status_update.new_chat_members,
    "forward": Filters.forwarded & ~ Filters.is_automatic_forward,
    "game": Filters.game,
    "location": Filters.location,
    "egame": Filters.dice,
    "rtl": "rtl",
    "button": "button",
    "inline": "inline",
    "apk" : Filters.document.mime_type("application/vnd.android.package-archive"),
    "doc" : Filters.document.mime_type("application/msword"),
    "exe" : Filters.document.mime_type("application/x-ms-dos-executable"),
    "gif" : Filters.document.mime_type("video/mp4"),
    "jpg" : Filters.document.mime_type("image/jpeg"),
    "mp3" : Filters.document.mime_type("audio/mpeg"),
    "pdf" : Filters.document.mime_type("application/pdf"),
    "txt" : Filters.document.mime_type("text/plain"),
    "xml" : Filters.document.mime_type("application/xml"),
    "zip" : Filters.document.mime_type("application/zip"),
}

LOCK_CHAT_RESTRICTION = {
    "all": {
        "can_send_messages": False,
        "can_send_media_messages": False,
        "can_send_polls": False,
        "can_send_other_messages": False,
        "can_add_web_page_previews": False,
        "can_change_info": False,
        "can_invite_users": False,
        "can_pin_messages": False,
    },
    "messages": {"can_send_messages": False},
    "media": {"can_send_media_messages": False},
    "sticker": {"can_send_other_messages": False},
    "gif": {"can_send_other_messages": False},
    "poll": {"can_send_polls": False},
    "other": {"can_send_other_messages": False},
    "previews": {"can_add_web_page_previews": False},
    "info": {"can_change_info": False},
    "invite": {"can_invite_users": False},
    "pin": {"can_pin_messages": False},
}

UNLOCK_CHAT_RESTRICTION = {
    "all": {
        "can_send_messages": True,
        "can_send_media_messages": True,
        "can_send_polls": True,
        "can_send_other_messages": True,
        "can_add_web_page_previews": True,
        "can_invite_users": True,
    },
    "messages": {"can_send_messages": True},
    "media": {"can_send_media_messages": True},
    "sticker": {"can_send_other_messages": True},
    "gif": {"can_send_other_messages": True},
    "poll": {"can_send_polls": True},
    "other": {"can_send_other_messages": True},
    "previews": {"can_add_web_page_previews": True},
    "info": {"can_change_info": True},
    "invite": {"can_invite_users": True},
    "pin": {"can_pin_messages": True},
}

PERM_GROUP = -8
REST_GROUP = -12


# NOT ASYNC
def restr_members(
    bot, chat_id, members, messages=False, media=False, other=False, previews=False
):
    for mem in members:
        try:
            bot.restrict_chat_member(
                chat_id,
                mem.user,
                can_send_messages=messages,
                can_send_media_messages=media,
                can_send_other_messages=other,
                can_add_web_page_previews=previews,
            )
        except TelegramError:
            pass


# NOT ASYNC
def unrestr_members(
    bot, chat_id, members, messages=True, media=True, other=True, previews=True
):
    for mem in members:
        try:
            bot.restrict_chat_member(
                chat_id,
                mem.user,
                can_send_messages=messages,
                can_send_media_messages=media,
                can_send_other_messages=other,
                can_add_web_page_previews=previews,
            )
        except TelegramError:
            pass

@rencmd(command='locktypes')
def locktypes(update, context):
    new_lock = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Support", url="https://t.me/pantekyks")]]
    )
    update.effective_message.reply_text(
        "\n • ".join(["Locks available: "] + sorted(list(LOCK_TYPES) + list(LOCK_CHAT_RESTRICTION))), reply_markup=new_lock)

@rencmd(command='lock', pass_args=True)
@connection_status
@typing_action
@bot_admin_check()
@user_admin_check(AdminPerms.CAN_CHANGE_INFO, allow_mods = True)
@loggable
def lock(update, context) -> str:  # sourcery no-metrics
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    if bot_is_admin(chat, AdminPerms.CAN_DELETE_MESSAGES):
        if len(args) >= 1:
            ltype = args[0].lower()
            if ltype == "anonchannel":
                text = "`anonchannel` is not a lock, please use `/antichannel on` to restrict channels"
                send_message(update.effective_message, text, parse_mode = "markdown")
            elif ltype in LOCK_TYPES:

                text = f"Locked {ltype} for non-admins!"
                sql.update_lock(chat.id, ltype, locked=True)
                send_message(update.effective_message, text, parse_mode="markdown")

                return f"<b>{html.escape(chat.title)}:</b>\n#LOCK\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\nLocked <code>{ltype}</code>."

            elif ltype in LOCK_CHAT_RESTRICTION:
                text = f"Locked {ltype} for all non-admins!"
                current_permission = context.bot.getChat(chat.id).permissions
                context.bot.set_chat_permissions(
                    chat_id=chat.id,
                    permissions=get_permission_list(
                        ast.literal_eval(str(current_permission)),
                        LOCK_CHAT_RESTRICTION[ltype.lower()],
                    ),
                )

                send_message(update.effective_message, text, parse_mode="markdown")
                return f"<b>{html.escape(chat.title)}:</b>\n#Permission_LOCK\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\nLocked <code>{ltype}</code>."

            else:
                send_message(
                    update.effective_message,
                    "What are you trying to lock...? Try /locktypes for the list of lockables",
                )
        else:
            send_message(update.effective_message, "What are you trying to lock...?")

    else:
        send_message(
            update.effective_message,
            "I am not administrator or haven't got enough rights.",
        )

    return ""

@rencmd(command='unlock', pass_args=True)
@bot_admin_check()
@typing_action
@user_admin_check()
@loggable
def unlock(update, context) -> str:  # sourcery no-metrics
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    if user_is_admin(update, user.id, allow_moderators=True):
        if len(args) >= 1:
            ltype = args[0].lower()
            if ltype == "anonchannel":
                text = "`anonchannel` is not a lock, please use `/antichannel off` to disable restricting channels"
                send_message(update.effective_message, text, parse_mode="markdown")
            elif ltype in LOCK_TYPES:
                text = f"Unlocked {ltype} for everyone!"
                sql.update_lock(chat.id, ltype, locked=False)
                send_message(update.effective_message, text, parse_mode="markdown")
                return f"<b>{html.escape(chat.title)}:</b>\n#UNLOCK\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\nUnlocked <code>{ltype}</code>."

            elif ltype in UNLOCK_CHAT_RESTRICTION:
                text = f"Unlocked {ltype} for everyone!"

                current_permission = context.bot.getChat(chat.id).permissions
                context.bot.set_chat_permissions(
                    chat_id=chat.id,
                    permissions=get_permission_list(
                        ast.literal_eval(str(current_permission)),
                        UNLOCK_CHAT_RESTRICTION[ltype.lower()],
                    ),
                )

                send_message(update.effective_message, text, parse_mode="markdown")

                return f"<b>{html.escape(chat.title)}:</b>\n#UNLOCK\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\nUnlocked <code>{ltype}</code>."
            else:
                send_message(
                    update.effective_message,
                    "What are you trying to unlock...? Try /locktypes for the list of lockables.",
                )

        else:
            send_message(update.effective_message, "What are you trying to unlock...?")

    return ""

@renmsg((Filters.all & Filters.chat_type.groups), group=PERM_GROUP)
@user_not_admin_check
def del_lockables(update, context):  # sourcery no-metrics
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    user = message.sender_chat or update.effective_user
    if is_approved(chat.id, user.id):
        return
    for lockable, filter in LOCK_TYPES.items():
        if lockable == "rtl":
            if sql.is_locked(chat.id, lockable) and bot_is_admin(chat, AdminPerms.CAN_DELETE_MESSAGES):
                if message.caption:
                    check = ad.detect_alphabet(f"{message.caption}")
                    if "ARABIC" in check:
                        try:
                            # replyyy = "This action is restricted to admins only!"
                            # message.reply_text(replyyy)
                            message.delete()
                        except BadRequest as excp:
                            if excp.message != "Message to delete not found":
                                log.exception("ERROR in lockables")
                        break
                if message.text:
                    check = ad.detect_alphabet(f"{message.text}")
                    if "ARABIC" in check:
                        try:
                            message.delete()
                        except BadRequest as excp:
                            if excp.message != "Message to delete not found":
                                log.exception("ERROR in lockables")
                        break
            continue
        if lockable == "button":
            if (
                sql.is_locked(chat.id, lockable)
                and bot_is_admin(chat, AdminPerms.CAN_DELETE_MESSAGES)
                and message.reply_markup
                and message.reply_markup.inline_keyboard
            ):
                try:
                    # replyyy = "This action is restricted to admins only!"
                    # message.reply_text(replyyy)
                    message.delete()
                except BadRequest as excp:
                    if excp.message != "Message to delete not found":
                        log.exception("ERROR in lockables")
                break
            continue
        if lockable == "inline":
            if (
                sql.is_locked(chat.id, lockable)
                and bot_is_admin(chat, AdminPerms.CAN_DELETE_MESSAGES)
                and message
                and message.via_bot
            ):
                try:               
                    message.delete()
                except BadRequest as excp:
                    if excp.message != "Message to delete not found":
                        log.exception("ERROR in lockables")
                break
            continue
        if (
            filter(update)
            and sql.is_locked(chat.id, lockable)
            and bot_is_admin(chat, AdminPerms.CAN_DELETE_MESSAGES)
        ):
            if lockable == "bots":
                new_members = update.effective_message.new_chat_members
                for new_mem in new_members:
                    if new_mem.is_bot:
                        if not bot_is_admin(chat, AdminPerms.CAN_RESTRICT_MEMBERS):
                            send_message(
                                update.effective_message,
                                "I see a bot and I've been told to stop them from joining..."
                                "but I'm not admin!",
                            )
                            return

                        chat.ban_member(new_mem.id)
                        send_message(
                            update.effective_message,
                            "Only admins are allowed to add bots in this chat! Get outta here.",
                        )
                        break
            else:
                try:                 
                    message.delete()
                except BadRequest as excp:
                    if excp.message != "Message to delete not found":
                        log.exception("ERROR in lockables")

                break


def build_lock_message(chat_id):
    locks = sql.get_locks(chat_id)
    res = ""
    locklist = []
    if locks:
        res += "*" + "These are the current locks in this Chat:" + "*"
        locklist.extend(
            (
                f"sticker = `{locks.sticker}`",
                f"audio = `{locks.audio}`",
                f"voice = `{locks.voice}`",
                f"document = `{locks.document}`",
                f"video = `{locks.video}`",
                f"contact = `{locks.contact}`",
                f"photo = `{locks.photo}`",
                f"gif = `{locks.gif}`",
                f"url = `{locks.url}`",
                f"bots = `{locks.bots}`",
                f"forward = `{locks.forward}`",
                f"game = `{locks.game}`",
                f"location = `{locks.location}`",
                f"rtl = `{locks.rtl}`",
                f"button = `{locks.button}`",
                f"egame = `{locks.egame}`",
                f"inline = `{locks.inline}`",
                f"apk = `{locks.apk}`",
                f"doc = `{locks.doc}`",
                f"exe = `{locks.exe}`",
                f"jpg = `{locks.jpg}`",
                f"mp3 = `{locks.mp3}`",
                f"pdf = `{locks.pdf}`",
                f"txt = `{locks.txt}`",
                f"xml = `{locks.xml}`",
                f"zip = `{locks.zip}`",
            )
        )
    permissions = dispatcher.bot.get_chat(chat_id).permissions
    permslist = [
        f"messages = `{permissions.can_send_messages}`",
        f"media = `{permissions.can_send_media_messages}`",
        f"poll = `{permissions.can_send_polls}`",
        f"other = `{permissions.can_send_other_messages}`",
        f"previews = `{permissions.can_add_web_page_previews}`",
        f"info = `{permissions.can_change_info}`",
        f"invite = `{permissions.can_invite_users}`",
        f"pin = `{permissions.can_pin_messages}`",
    ]
    if locklist:
        # Ordering lock list
        locklist.sort()
        # Building lock list string
        for x in locklist:
            res += f"\n • {x}"
    res += "\n\n*" + "These are the current chat permissions:" + "*"
    for x in permslist:
        res += f"\n • {x}"
    return res

@rencmd(command='locks')
@connection_status
@user_admin_check(AdminPerms.CAN_CHANGE_INFO, allow_mods=True)
@typing_action
def list_locks(update, _):
    chat = update.effective_chat  # type: Optional[Chat]

    res = build_lock_message(chat.id)


    send_message(update.effective_message, res, parse_mode=ParseMode.MARKDOWN)


def get_permission_list(current, new):
    permissions = {
        "can_send_messages": None,
        "can_send_media_messages": None,
        "can_send_polls": None,
        "can_send_other_messages": None,
        "can_add_web_page_previews": None,
        "can_change_info": None,
        "can_invite_users": None,
        "can_pin_messages": None,
    }
    permissions |= current
    permissions.update(new)
    return ChatPermissions(**permissions)


def __import_data__(chat_id, data):
    # set chat locks
    locks = data.get("locks", {})
    for itemlock in locks:
        if itemlock in LOCK_TYPES:
            sql.update_lock(chat_id, itemlock, locked=True)
        elif itemlock in LOCK_CHAT_RESTRICTION:
            sql.update_restriction(chat_id, itemlock, locked=True)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    return build_lock_message(chat_id)


from .language import gs

def get_help(chat):
    return gs(chat, "locks_help")

__mod_name__ = "Locks"

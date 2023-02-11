from enum import Enum
from cachetools import TTLCache

from telegram import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ParseMode,
    Message,
    Update,
    message,
)

from kyosuke import (
    OWNER_ID,
    SYS_ADMIN,
    DEV_USERS,
    MOD_USERS,
    SUDO_USERS,
    SUPPORT_USERS,
    WHITELIST_USERS,
)

# stores admin in memory for 10 min.
ADMINS_CACHE = TTLCache(maxsize=512, ttl=60 * 30)

# stores bot admin status in memory for 10 min.
BOT_ADMIN_CACHE = TTLCache(maxsize=512, ttl=60 * 30)

DEV_USERS = DEV_USERS

SUDO_USERS = SUDO_USERS + DEV_USERS

WHITELIST_USERS = WHITELIST_USERS + SUDO_USERS

SUPPORT_USERS = SUPPORT_USERS + SUDO_USERS

MOD_USERS = MOD_USERS + SUDO_USERS


class AdminPerms(Enum):
    CAN_RESTRICT_MEMBERS = "can_restrict_members"
    CAN_PROMOTE_MEMBERS = "can_promote_members"
    CAN_INVITE_USERS = "can_invite_users"
    CAN_DELETE_MESSAGES = "can_delete_messages"
    CAN_CHANGE_INFO = "can_change_info"
    CAN_PIN_MESSAGES = "can_pin_messages"
    IS_ANONYMOUS = "is_anonymous"


class ChatStatus(Enum):
    CREATOR = "creator"
    ADMIN = "administrator"


# class SuperUsers(Enum):
# 	Owner = [OWNER_ID]
# 	SysAdmin = [OWNER_ID, SYS_ADMIN]
# 	Devs = DEV_USERS
# 	Sudos = SUDO_USERS
# 	Supports = SUPPORT_USERS
# 	Whitelist = WHITELIST_USERS
# 	Mods = MOD_USERS


def anon_reply_markup(cb_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="Prove identity", callback_data=cb_id)]]
    )


anon_reply_text = (
    "Seems like you're anonymous, click the button below to prove your identity"
)


def edit_anon_msg(msg: Message, text: str):
    """
    edit anon check message and remove the button
    """
    msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=None)


def user_is_not_admin_errmsg(
    msg: Message, permission: AdminPerms = None, cb: CallbackQuery = None
):
    errmsg = (
        f"You lack the following permission for this command:\n`{permission.value}`!"
    )
    if cb:
        return cb.answer(errmsg, show_alert=True)
    return msg.reply_text(errmsg, parse_mode=ParseMode.MARKDOWN)


def button_expired_error(u: Update):
    errmsg = f"This button has expired!"
    if u.callback_query:
        u.callback_query.answer(errmsg, show_alert=True)
        u.effective_message.delete()
        return
    return u.effective_message.edit_text(errmsg, parse_mode=ParseMode.MARKDOWN)


anon_callbacks = {}

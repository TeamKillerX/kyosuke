from functools import wraps
from typing import Optional
from threading import RLock

from telegram import Chat, Update, ChatMember
from telegram.ext import CallbackContext as Ctx, CallbackQueryHandler as CBHandler

from kyosuke import dispatcher

from .admin_status_helpers import (
    ADMINS_CACHE as A_CACHE,
    BOT_ADMIN_CACHE as B_CACHE,
    SUDO_USERS,
    MOD_USERS,
    AdminPerms,
    anon_reply_markup as arm,
    anon_reply_text as art,
    anon_callbacks as a_cb,
    user_is_not_admin_errmsg as u_na_errmsg,
    edit_anon_msg as eam,
    button_expired_error as bxp,
)


def bot_is_admin(chat: Chat, perm: Optional[AdminPerms] = None) -> bool:
    if chat.type == "private" or chat.all_members_are_administrators:
        return True

    bot_member = get_bot_member(chat.id)

    if perm:
        return getattr(bot_member, perm.value)

    return bot_member.status == "administrator"  # bot can't be owner


def get_bot_member(chat_id: int) -> ChatMember:
    try:
        return B_CACHE[chat_id]
    except KeyError:
        mem = dispatcher.bot.getChatMember(chat_id, dispatcher.bot.id)
        B_CACHE[chat_id] = mem
        return mem


# decorator, can be used as
# @bot_perm_check() with no perm to check for admin-ship only
# or as @bot_perm_check(AdminPerms.value) to check for a specific permission
def bot_admin_check(permission: AdminPerms = None):
    def wrapper(func):
        @wraps(func)
        def wrapped(update: Update, context: Ctx, *args, **kwargs):
            nonlocal permission
            chat = update.effective_chat
            if chat.type == "private" or chat.all_members_are_administrators:
                return func(update, context, *args, **kwargs)
            bot_id = dispatcher.bot.id

            try:  # try to get from cache
                bot_member = B_CACHE[chat.id]
            except KeyError:  # if not in cache, get from API and save to cache
                bot_member = dispatcher.bot.getChatMember(chat.id, bot_id)
                B_CACHE[chat.id] = bot_member

            if permission:  # if a perm is required, check for it
                if getattr(bot_member, permission.value):
                    func(update, context, *args, **kwargs)
                    return
                return update.effective_message.reply_text(
                    f"I can't perform this action due to missing permissions;\n"
                    f"Make sure i am an admin and {permission.name.lower().replace('is_', 'am ').replace('_', ' ')}!"
                )

            if (
                bot_member.status == "administrator"
            ):  # if no perm is required, check for admin-ship only
                return func(update, context, *args, **kwargs)
            else:  # not admin
                return update.effective_message.reply_text(
                    "I can't perform this action because I'm not admin!"
                )

        return wrapped

    return wrapper


def user_is_admin(
    update: Update,
    user_id: int,
    channels: bool = False,  # if True, returns True if user is anonymous
    allow_moderators: bool = False,  # if True, returns True if user is a moderator
    perm: AdminPerms = None,  # if not None, returns True if user has the specified permission
) -> bool:
    chat = update.effective_chat
    message = update.effective_message
    if chat.type == "private" or user_id in (
        MOD_USERS if allow_moderators else SUDO_USERS
    ):
        return True

    if channels and (
        message.sender_chat is not None and message.sender_chat.type != "channel"
    ):
        return True  # return true if user is anonymous

    member: ChatMember = get_mem_from_cache(user_id, chat.id)

    if not member:  # not in cache so not an admin
        return False

    if perm:  # check perm if its required
        try:
            the_perm = perm.value
        except AttributeError:
            return bxp(update)
        return getattr(member, the_perm) or member.status == "creator"

    return member.status in ["administrator", "creator"]  # check if user is admin


RLOCK = RLock()


def get_mem_from_cache(user_id: int, chat_id: int) -> ChatMember:
    with RLOCK:
        try:
            for i in A_CACHE[chat_id]:
                if i.user.id == user_id:
                    return i

        except KeyError:
            admins = dispatcher.bot.getChatAdministrators(chat_id)
            A_CACHE[chat_id] = admins
            for i in admins:
                if i.user.id == user_id:
                    return i


# decorator, can be used as @bot_admin_check() to check user is admin
# or @bot_admin_check(AdminPerms.value) to check for a specific permission
# ustat can be used in both cases to allow moderators to use the command
def user_admin_check(
    permission: AdminPerms = None, allow_mods: bool = False, noreply: bool = False
):
    def wrapper(func):
        @wraps(func)
        def wrapped(update: Update, context: Ctx, *args, **kwargs):
            nonlocal permission
            if update.effective_chat.type == "private":
                return func(update, context, *args, **kwargs)
            message = update.effective_message

            if update.effective_message.sender_chat:  # anonymous sender
                # callback contains chat_id, message_id, and the required perm
                callback_id = f'anonCB/{message.chat.id}/{message.message_id}/{permission.value if permission else "None"}'
                # store the function to be called in a (chat_id, message_id) tuple
                # stored data will be (update, context), func, callback message_id
                a_cb[(message.chat.id, message.message_id)] = (
                    (update, context),
                    func,
                    (message, args),
                )
                message.reply_text(text=art, reply_markup=arm(callback_id))

            # not anon so just check for admin/perm
            else:
                user_id = (
                    message.from_user.id if not noreply else update.effective_user.id
                )
                if user_is_admin(
                    update,
                    user_id,
                    allow_moderators=allow_mods,  # allow moderators only if ustat is MOD_USERS
                    perm=permission,
                ):
                    return func(update, context, *args, **kwargs)

                return u_na_errmsg(message, permission, update.callback_query)

        return wrapped

    return wrapper


# decorator, can be used as @user_not_admin_check to check user is not admin
def user_not_admin_check(func):
    @wraps(func)
    def wrapped(update: Update, context: Ctx, *args, **kwargs):
        message = update.effective_message
        user = message.sender_chat or update.effective_user
        if (
            message.is_automatic_forward
            or (message.sender_chat and message.sender_chat.type != "channel")
            or not user
        ):
            return
        elif not user_is_admin(update, user.id, channels=True):
            return func(update, context, *args, **kwargs)
        return

    return wrapped


def perm_callback_check(upd: Update, _: Ctx):
    callback = upd.callback_query
    chat_id = int(callback.data.split("/")[1])
    message_id = int(callback.data.split("/")[2])
    perm = callback.data.split("/")[3]
    user_id = callback.from_user.id
    msg = upd.effective_message

    mem = user_is_admin(upd, user_id, perm=perm if perm != "None" else None)

    if not mem:  # not admin or doesn't have the required perm
        eam(
            msg,
            "You need to be an admin to perform this action!"
            if not perm == "None"
            else f"You lack the permission: `{perm}`!",
        )
        return

    try:
        cb = a_cb.pop((chat_id, message_id), None)
    except KeyError:
        eam(msg, "This message is no longer valid.")
        return

    msg.delete()

    # update the `Update` and `CallbackContext` attributes by the correct values, so they can be used properly
    setattr(cb[0][0], "_effective_user", upd.effective_user)
    setattr(cb[0][0], "_effective_message", cb[2][0])

    return cb[1](cb[0][0], cb[0][1])  # return func(update, context)


dispatcher.add_handler(CBHandler(perm_callback_check, pattern="anonCB", run_async=True))

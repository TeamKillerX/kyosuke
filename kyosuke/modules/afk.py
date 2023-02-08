#  Copyright (C) 2017-2019, Paul Larsen

import contextlib
import time

from telegram import MessageEntity, ParseMode, Update
from telegram.error import BadRequest
from telegram.ext import CallbackContext, Filters, MessageHandler

from kyosuke import dispatcher, REDIS
from kyosuke.modules.disable import (
     DisableAbleCommandHandler,
     DisableAbleMessageHandler,
)
from kyosuke.modules.helper_funcs.readable_time import get_readable_time
from kyosuke.database.redis.afk_redis import (
     start_afk,
     end_afk,
     is_user_afk,
     afk_reason,
)
from kyosuke.modules.users import get_user_id
from .helper_funcs.decorators import rencmd, renmsg
from .helper_funcs.filters import CustomFilters

@rencmd(command="afk", pass_args=True)
@renmsg(Filters.regex("(?i)^brb"), group=10)
def afk(update: Update, _: CallbackContext):
    message = update.effective_message
    args = message.text.split(None, 1)
    user = update.effective_user

    if not user or user.id in (777000, 1087968824, 136817688):  # ignore channels
        return

    start_afk_time = time.time()
    reason = args[1] if len(args) >= 2 else "none"
    start_afk(user.id, reason)
    REDIS.set(f"afk_time_{user.id}", start_afk_time)
    fname = user.first_name
    with contextlib.suppress(BadRequest):
        message.reply_text(
            f"<code>{fname}</code> is now AFK!", parse_mode=ParseMode.HTML
        )

@renmsg((Filters.all & Filters.chat_type.groups), group=7)
def no_longer_afk(update: Update, _: CallbackContext):
    user = update.effective_user
    message = update.effective_message

    if not user:  # ignore channels
        return

    if not is_user_afk(user.id):  # Check if user is afk or not
        return

    x = REDIS.get(f"afk_time_{user.id}")
    if not x:
        return

    end_afk_time = get_readable_time((time.time() - float(x)))
    REDIS.delete(f"afk_time_{user.id}")
    if res := end_afk(user.id):
        if message.new_chat_members:  # don't say message
            return
        firstname = user.first_name
        try:
            message.reply_text(
                f"<b>{firstname}</b> is back online!\n"
                f"You were away for: <code>{end_afk_time}</code>",
                parse_mode=ParseMode.HTML,
            )
        except BadRequest:
            return

@renmsg((Filters.all & Filters.chat_type.groups), group=8)
def reply_afk(update: Update, context: CallbackContext):
    message = update.effective_message
    userc = update.effective_user
    userc_id = userc.id
    if message.entities and message.parse_entities(
        [MessageEntity.TEXT_MENTION, MessageEntity.MENTION]
    ):
        entities = message.parse_entities(
            [MessageEntity.TEXT_MENTION, MessageEntity.MENTION]
        )

        chk_users = []
        for ent in entities:
            if ent.type == MessageEntity.TEXT_MENTION:
                user_id = ent.user.id
                fst_name = ent.user.first_name

                if user_id in chk_users:
                    return
                chk_users.append(user_id)

            elif ent.type == MessageEntity.MENTION:
                user_id = get_user_id(
                    message.text[ent.offset : ent.offset + ent.length]
                )
                if not user_id:
                    # Should never happen, since for a user to become AFK they must have spoken. Maybe changed username?
                    return

                if user_id in chk_users:
                    return
                chk_users.append(user_id)

                try:
                    chat = context.bot.get_chat(user_id)
                except BadRequest as e:
                    print(
                        f"Error: Could not fetch userid {user_id} for AFK module due to {e}"
                    )
                    return
                fst_name = chat.first_name

            else:
                return

            check_afk(update, context, user_id, fst_name, userc_id)

    elif message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        fst_name = message.reply_to_message.from_user.first_name
        check_afk(update, context, user_id, fst_name, userc_id)


def check_afk(
    update: Update, _: CallbackContext, user_id: int, fst_name: str, userc_id: int
):
    message = update.effective_message
    if is_user_afk(user_id):
        reason = afk_reason(user_id)
        z = REDIS.get(f"afk_time_{user_id}")
        if not z:
            return

        since_afk = get_readable_time((time.time() - float(z)))
        if userc_id == user_id:
            return
        if reason == "none":
            res = f"<b>{fst_name}</b> is AFK!\nLast seen: <code>{since_afk}</code>"
        else:
            res = f"<b>{fst_name}</b> is AFK!\nReason: {reason}\nLast seen: {since_afk}"

        message.reply_text(res, parse_mode=ParseMode.HTML)


def __gdpr__(user_id):
    end_afk(user_id)


from .language import gs

def get_help(chat):
    return gs(chat, "afk_help")

__mod_name__ = "AFK"
__command_list__ = ["afk"]

import html
import json
import os
from typing import List, Optional

from telegram import Update, ParseMode, TelegramError
from telegram.ext import CallbackContext
from telegram.utils.helpers import mention_html

from kyosuke import (
    dispatcher,
    WHITELIST_USERS,
    SARDEGNA_USERS,
    SUPPORT_USERS,
    SUDO_USERS,
    DEV_USERS,
    OWNER_ID,
)
from kyosuke.modules.helper_funcs.chat_status import whitelist_plus, dev_plus, sudo_plus
from kyosuke.modules.helper_funcs.extraction import extract_user
from kyosuke.modules.log_channel import gloggable
from kyosuke.modules.sql import nation_sql as sql
from kyosuke.modules.helper_funcs.decorators import rencmd

def check_user_id(user_id: int, context: CallbackContext) -> Optional[str]:
    bot = context.bot
    if not user_id:
        return "That...is a chat! baka ka omae?"

    elif user_id == bot.id:
        return "This does not work that way."

    else:
        return None

@rencmd(command='addsudo')
@dev_plus
@gloggable
def addsudo(update: Update, context: CallbackContext) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)
    rt = ""

    if reply := check_user_id(user_id, bot):
        message.reply_text(reply)
        return ""

    if user_id in SUDO_USERS:
        message.reply_text("This member is already a Sudo user")
        return ""

    if user_id in SUPPORT_USERS:
        rt += "Requested kyosuke Union to promote a Support user to Sudo."
        SUPPORT_USERS.remove(user_id)

    if user_id in WHITELIST_USERS:
        rt += "Requested Kyosuke Union to promote a Whitelist user to Sudo."
        WHITELIST_USERS.remove(user_id)

    # will add or update their role
    sql.set_royal_role(user_id, "sudos")
    SUDO_USERS.append(user_id)

    update.effective_message.reply_text(
        f"{rt}\nSuccessfully promoted {user_member.first_name} to Sudo!"
    )

    log_message = (
        f"#SUDO\n"
        f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
        f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
    )

    if chat.type != "private":
        log_message = f"<b>{html.escape(chat.title)}:</b>\n{log_message}"

    return log_message


@rencmd(command='addsupport')
@sudo_plus
@gloggable
def addsupport(
    update: Update,
    context: CallbackContext,
) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)
    rt = ""

    if reply := check_user_id(user_id, bot):
        message.reply_text(reply)
        return ""

    if user_id in SUDO_USERS:
        rt += "Requested Eagle Union to demote this Sudo to Support"
        SUDO_USERS.remove(user_id)

    if user_id in SUPPORT_USERS:
        message.reply_text("This user is already a Support user.")
        return ""

    if user_id in WHITELIST_USERS:
        rt += "Requested Eagle Union to promote this Whitelist user to Support"
        WHITELIST_USERS.remove(user_id)

    sql.set_royal_role(user_id, "supports")
    SUPPORT_USERS.append(user_id)

    update.effective_message.reply_text(
        f"{rt}\n{user_member.first_name} was added as a Support user!"
    )

    log_message = (
        f"#SUPPORT\n"
        f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
        f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
    )

    if chat.type != "private":
        log_message = f"<b>{html.escape(chat.title)}:</b>\n{log_message}"

    return log_message


@rencmd(command='addwhitelist')
@sudo_plus
@gloggable
def addwhitelist(update: Update, context: CallbackContext) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)
    rt = ""

    if reply := check_user_id(user_id, bot):
        message.reply_text(reply)
        return ""

    if user_id in SUDO_USERS:
        rt += "This member is a Sudo user, Demoting to Whitelisted user."
        SUDO_USERS.remove(user_id)

    if user_id in SUPPORT_USERS:
        rt += "This user is already a Support user, Demoting to Whitelisted user."
        SUPPORT_USERS.remove(user_id)

    if user_id in WHITELIST_USERS:
        message.reply_text("This user is already a Whitelist user.")
        return ""

    sql.set_royal_role(user_id, "whitelists")
    WHITELIST_USERS.append(user_id)

    update.effective_message.reply_text(
        f"{rt}\nSuccessfully promoted {user_member.first_name} to a Whitelist user!"
    )

    log_message = (
        f"#WHITELIST\n"
        f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))} \n"
        f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
    )

    if chat.type != "private":
        log_message = f"<b>{html.escape(chat.title)}:</b>\n{log_message}"

    return log_message


@rencmd(command='addsardegna')
@sudo_plus
@gloggable
def addsardegna(update: Update, context: CallbackContext) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)
    rt = ""

    if reply := check_user_id(user_id, bot):
        message.reply_text(reply)
        return ""

    if user_id in SUDO_USERS:
        rt += "This member is a Sudo user, Demoting to Sardegna."
        SUDO_USERS.remove(user_id)

    if user_id in SUPPORT_USERS:
        rt += "This user is already a Support user, Demoting to Sardegna."
        SUPPORT_USERS.remove(user_id)

    if user_id in WHITELIST_USERS:
        rt += "This user is already a Whitelist user, Demoting to Sardegna."
        WHITELIST_USERS.remove(user_id)

    if user_id in SARDEGNA_USERS:
        message.reply_text("This user is already a Sardegna.")
        return ""

    sql.set_royal_role(user_id, "sardegnas")
    SARDEGNA_USERS.append(user_id)

    update.effective_message.reply_text(
        f"{rt}\nSuccessfully promoted {user_member.first_name} to a Sardegna Nation!"
    )

    log_message = (
        f"#SARDEGNA\n"
        f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))} \n"
        f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
    )

    if chat.type != "private":
        log_message = f"<b>{html.escape(chat.title)}:</b>\n{log_message}"

    return log_message


@rencmd(command=["removesudo", "rmsudo"])
@dev_plus
@gloggable
def removesudo(update: Update, context: CallbackContext) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)

    if reply := check_user_id(user_id, bot):
        message.reply_text(reply)
        return ""

    if user_id in SUDO_USERS:
        message.reply_text("Requested Eagle Union to demote this user to Civilian")
        SUDO_USERS.remove(user_id)
        sql.remove_royal(user_id)

        log_message = (
            f"#UNSUDO\n"
            f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
            f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
        )

        if chat.type != "private":
            log_message = f"<b>{html.escape(chat.title)}:</b>\n{log_message}"

        return log_message

    else:
        message.reply_text("This user is not a Sudo user!")
        return ""


@rencmd(command=["removesupport", "rmsupport"])
@sudo_plus
@gloggable
def removesupport(update: Update, context: CallbackContext) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)

    if reply := check_user_id(user_id, bot):
        message.reply_text(reply)
        return ""

    if user_id in SUPPORT_USERS:
        message.reply_text("Requested Eagle Union to demote this user to Civilian")
        SUPPORT_USERS.remove(user_id)
        sql.remove_royal(user_id)

        log_message = (
            f"#UNSUPPORT\n"
            f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
            f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
        )

        if chat.type != "private":
            log_message = f"<b>{html.escape(chat.title)}:</b>\n{log_message}"

        return log_message

    else:
        message.reply_text("This user is not a Support user!")
        return ""


@rencmd(command='removewhitelist')
@sudo_plus
@gloggable
def removewhitelist(update: Update, context: CallbackContext) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)

    if reply := check_user_id(user_id, bot):
        message.reply_text(reply)
        return ""

    if user_id in WHITELIST_USERS:
        message.reply_text("Demoting to normal user")
        WHITELIST_USERS.remove(user_id)
        sql.remove_royal(user_id)

        log_message = (
            f"#UNWHITELIST\n"
            f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
            f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
        )

        if chat.type != "private":
            log_message = f"<b>{html.escape(chat.title)}:</b>\n{log_message}"

        return log_message
    else:
        message.reply_text("This user is not a Whitelist user!")
        return ""


@rencmd(command='removesardegna')
@sudo_plus
@gloggable
def removesardegna(update: Update, context: CallbackContext) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)

    if reply := check_user_id(user_id, bot):
        message.reply_text(reply)
        return ""

    if user_id in SARDEGNA_USERS:
        message.reply_text("Demoting to normal user")
        SARDEGNA_USERS.remove(user_id)
        sql.remove_royal(user_id)

        log_message = (
            f"#UNSARDEGNA\n"
            f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
            f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
        )

        if chat.type != "private":
            log_message = f"<b>{html.escape(chat.title)}:</b>\n{log_message}"

        return log_message
    else:
        message.reply_text("This user is not a Sardegna Nation!")
        return ""

# I added extra new lines
nations = """ kyosuke has bot access levels we call as *"Nation Levels"*
\n*kyosuke Union* - Devs who can access the bots server and can execute, edit, modify bot code. Can also manage other Nations
\n*God* - Only one exists, bot owner.
Owner has complete bot access, including bot adminship in chats kyosuke is at.
\n*Royals* - Have super user access, can gban, manage Nations lower than them and are admins in Hito.
\n*Sakuras* - Have access go globally ban users across kyosuke.
\n*Sardegnas* - Same as Neptunians but can unban themselves if banned.
\n*Neptunians* - Cannot be banned, muted flood kicked but can be manually banned by admins.
\n*Disclaimer*: The Nation levels in kyosuke are there for troubleshooting, support, banning potential scammers.
Report abuse or ask us more on these at [JAMET](https://t.me/pantekyks).
"""


def send_nations(update):
    update.effective_message.reply_text(
        nations, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
    )

@rencmd(command='removesardegna')
@whitelist_plus
def whitelistlist(update: Update, context: CallbackContext):
    bot = context.bot
    reply = "<b>Known Neptunia Nations :</b>\n"
    for each_user in WHITELIST_USERS:
        user_id = int(each_user)
        try:
            user = bot.get_chat(user_id)

            reply += f"• {mention_html(user_id, user.first_name)}\n"
        except TelegramError:
            pass
    update.effective_message.reply_text(reply, parse_mode=ParseMode.HTML)

@rencmd(command='sardegnas')
@whitelist_plus
def Sardegnalist(update: Update, context: CallbackContext):
    bot = context.bot
    reply = "<b>Known Sardegna Nations :</b>\n"
    for each_user in SARDEGNA_USERS:
        user_id = int(each_user)
        try:
            user = bot.get_chat(user_id)
            reply += f"• {mention_html(user_id, user.first_name)}\n"
        except TelegramError:
            pass
    update.effective_message.reply_text(reply, parse_mode=ParseMode.HTML)

@rencmd(command=["supportlist", "sakuras"])
@whitelist_plus
def supportlist(update: Update, context: CallbackContext):
    bot = context.bot
    reply = "<b>Known Sakura Nations :</b>\n"
    for each_user in SUPPORT_USERS:
        user_id = int(each_user)
        try:
            user = bot.get_chat(user_id)
            reply += f"• {mention_html(user_id, user.first_name)}\n"
        except TelegramError:
            pass
    update.effective_message.reply_text(reply, parse_mode=ParseMode.HTML)

@rencmd(command=["sudolist", "royals"])
@whitelist_plus
def sudolist(update: Update, context: CallbackContext):
    bot = context.bot
    true_sudo = list(set(SUDO_USERS) - set(DEV_USERS))
    reply = "<b>Known Royal Nations :</b>\n"
    for each_user in true_sudo:
        user_id = int(each_user)
        try:
            user = bot.get_chat(user_id)
            reply += f"• {mention_html(user_id, user.first_name)}\n"
        except TelegramError:
            pass
    update.effective_message.reply_text(reply, parse_mode=ParseMode.HTML)

@rencmd(command='devlist')
@whitelist_plus
def devlist(update: Update, context: CallbackContext):
    bot = context.bot
    true_dev = tuple(set(DEV_USERS) - {OWNER_ID})
    reply = "<b>Kyosuke Union Members :</b>\n"
    for each_user in true_dev:
        user_id = int(each_user)
        try:
            user = bot.get_chat(user_id)
            reply += f"• {mention_html(user_id, user.first_name)}\n"
        except TelegramError:
            pass
    update.effective_message.reply_text(reply, parse_mode=ParseMode.HTML)


__mod_name__ = "Nations"

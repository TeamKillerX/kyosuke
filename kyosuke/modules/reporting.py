import html

from kyosuke import log, SUDO_USERS, WHITELIST_USERS
from .log_channel import loggable
from .sql import reporting_sql as sql
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Update
from telegram.error import BadRequest
from telegram.ext import (
    CallbackContext,
    Filters,
)
import kyosuke.modules.sql.log_channel_sql as logsql
from telegram.utils.helpers import mention_html
from .helper_funcs.decorators import rencmd, renmsg, rencallback
from .helper_funcs.admin_status import (
    user_admin_check,
    bot_admin_check,
    AdminPerms,
    user_not_admin_check,
    A_CACHE
)

REPORT_GROUP = 12
REPORT_IMMUNE_USERS = SUDO_USERS + WHITELIST_USERS

@rencmd(command='reports', run_async=True)
@bot_admin_check()
@user_admin_check(AdminPerms.CAN_CHANGE_INFO, allow_mods=True)
def report_setting(update: Update, context: CallbackContext):
    bot, args = context.bot, context.args
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user

    if len(args) >= 1:
        if args[0] in ("yes", "on"):
            sql.set_chat_setting(chat.id, True)
            msg.reply_text(
                "Turned on reporting! Admins who have turned on reports will be notified when /report "
                "or @admin is called."
            )

        elif args[0] in ("no", "off"):
            sql.set_chat_setting(chat.id, False)
            msg.reply_text(
                "Turned off reporting! No admins will be notified on /report or @admin."
            )
    else:
        msg.reply_text(
            f"This group's current setting is: `{sql.chat_should_report(chat.id)}`",
            parse_mode=ParseMode.MARKDOWN,
        )


@rencmd(command='report', filters=Filters.chat_type.groups, group=REPORT_GROUP, run_async=True)
@renmsg((Filters.regex(r"(?i)@admin(s)?")), group=REPORT_GROUP, run_async=True)
@user_not_admin_check
@loggable
def report(update: Update, context: CallbackContext) -> str:
    # sourcery no-metrics
    global reply_markup
    bot = context.bot
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    
    log_setting = logsql.get_chat_setting(chat.id)
    if not log_setting:
        logsql.set_chat_setting(logsql.LogChannelSettings(chat.id, True, True, True, True, True))
        log_setting = logsql.get_chat_setting(chat.id)

    if chat and message.reply_to_message and sql.chat_should_report(chat.id):
        reported_user = message.reply_to_message.from_user

        if user.id == reported_user.id:
            message.reply_text("Uh yeah, Sure sure...maso much?")
            return ""

        if reported_user.id == bot.id:
            message.reply_text("Nice try.")
            return ""

        if reported_user.id in REPORT_IMMUNE_USERS:
            message.reply_text("Uh? You reporting a Super user?")
            return ""

        admin_list = [i.user.id for i in A_CACHE[chat.id] if not (i.user.is_bot or i.is_anonymous)]

        if reported_user.id in admin_list:
            message.reply_text("Why are you reporting an admin?")
            return ""

        if message.sender_chat:
            reported = "Reported to admins."
            for admin in admin_list:
                try:
                    reported += f"<a href=\"tg://user?id={admin}\">\u2063</a>"
                except BadRequest:
                    log.exception(f"Exception while reporting user: {user} in chat: {chat.id}")
            message.reply_text(reported, parse_mode = ParseMode.HTML)

        message = update.effective_message
        msg = (
            f"<b>⚠️ Report: </b>{html.escape(chat.title)}\n"
            f"<b> • Report by:</b> {mention_html(user.id, user.first_name)}(<code>{user.id}</code>)\n"
            f"<b> • Reported user:</b> {mention_html(reported_user.id, reported_user.first_name)} (<code>{reported_user.id}</code>)\n"
        )
        tmsg = ""
        for admin in admin_list:
            link = mention_html(admin, "​")  # contains 0 width chatacters
            tmsg += link

        keyboard2 = [
            [
                InlineKeyboardButton(
                    "⚠ Kick",
                    callback_data=f"reported_{chat.id}=kick={reported_user.id}",
                ),
                InlineKeyboardButton(
                    "⛔️ Ban",
                    callback_data=f"reported_{chat.id}=banned={reported_user.id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "❎ Delete Message",
                    callback_data=f"reported_{chat.id}=delete={reported_user.id}={message.reply_to_message.message_id}",
                ),
                InlineKeyboardButton(
                    "❌ Close Panel",
                    callback_data=f"reported_{chat.id}=close={reported_user.id}",
                )
            ],
            [
                InlineKeyboardButton(
                        "📝 Read the rules", url="t.me/{}?start={}".format(bot.username, chat.id)
                    )
            ],
        ]
        reply_markup2 = InlineKeyboardMarkup(keyboard2)
        reportmsg = f"{mention_html(reported_user.id, reported_user.first_name)} was reported to the admins."
        reportmsg += tmsg
        message.reply_text(
            reportmsg,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup2
        )
        if not log_setting.log_report:
            return ""
        return msg
    return ""


@rencallback(pattern=r"reported_")
@bot_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS)
@user_admin_check(AdminPerms.CAN_RESTRICT_MEMBERS, allow_mods=True, noreply = True)
def buttons(update: Update, context: CallbackContext):
    bot = context.bot
    query = update.callback_query
    splitter = query.data.replace("reported_", "").split("=")
    if splitter[1] == "kick":
        try:
            bot.ban_chat_member(splitter[0], splitter[2])
            bot.unban_chat_member(splitter[0], splitter[2])
            query.answer("✅ Succesfully kicked")
            return ""
        except Exception as err:
            query.answer(f"🛑 Failed to kick\n{err}")           
    elif splitter[1] == "banned":
        try:
            bot.ban_chat_member(splitter[0], splitter[2])
            query.answer("✅  Succesfully Banned")
            return ""
        except Exception as err:            
            query.answer(f"🛑 Failed to Ban\n{err}", show_alert=True)
    elif splitter[1] == "delete":
        try:
            bot.deleteMessage(splitter[0], splitter[3])
            query.answer("✅ Message Deleted")
            
            kyb_no_del = [
                [
                    InlineKeyboardButton(
                        "⚠ Kick",
                        callback_data=f"reported_{splitter[0]}=kick={splitter[2]}",
                    ),
                    InlineKeyboardButton(
                        "⛔️ Ban",
                        callback_data=f"reported_{splitter[0]}=banned={splitter[2]}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "❌ Close Panel",
                        callback_data=f"reported_{splitter[0]}=close={splitter[2]}",
                    )
                ],
                [
                    InlineKeyboardButton(
                            "📝 Read the rules", url="t.me/{}?start={}".format(bot.username, splitter[0]),
                        )
                ],
            ]
            
            query.edit_message_reply_markup(
                InlineKeyboardMarkup(kyb_no_del)
            )
            return ""
        except Exception as err:
            query.answer(
                text=f"🛑 Failed to delete message!\n{err}",
                show_alert=True
            )
            
    elif splitter[1] == "close":
        try:
            query.answer("✅ Panel Closed!")
            
            kyb_no_del = [
                [
                    InlineKeyboardButton(
                            "📝 Read the rules", url="t.me/{}?start={}".format(bot.username, splitter[0]),
                        )
                ],
            ]
            
            query.edit_message_reply_markup(
                InlineKeyboardMarkup(kyb_no_del)
            )
            return ""
        except Exception as err:
            query.answer(
                text=f"🛑 Failed to close panel!\n{err}",
                show_alert=True
            )
         

def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, _):
    return f"This chat is setup to send user reports to admins, via /report and @admin: `{sql.chat_should_report(chat_id)}`"


def __user_settings__(user_id):
    if sql.user_should_report(user_id) is True:
        return "You will receive reports from chats you're admin."
    else:
        return "You will *not* receive reports from chats you're admin."


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)

def __chat_settings__(chat_id, _):
    return f"This chat is setup to send user reports to admins, via /report and @admin: `{sql.chat_should_report(chat_id)}`"

def __user_settings__(user_id):
    if sql.user_should_report(user_id) is True:
        return "You will receive reports from chats you're admin."
    else:
        return "You will *not* receive reports from chats you're admin."


from .language import gs


def get_help(chat):
    return gs(chat, "reports_help")


__mod_name__ = "Reporting"

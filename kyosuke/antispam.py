from . import DEV_USERS, SYS_ADMIN, dispatcher, OWNER_ID, j
from .modules.helper_funcs.admin_status import bot_is_admin, AdminPerms

Owner = OWNER_ID
NoResUser = [OWNER_ID, 777000, SYS_ADMIN] + DEV_USERS
AntiSpamValue = 25

GLOBAL_USER_DATA = {}
IGNORED_USERS = []
IGNORED_CHATS = []
ERRORS = []


def antispam_restrict_user(user_id, time):
	if user_id in NoResUser:
		return True
	if (GLOBAL_USER_DATA.get(user_id)
			and GLOBAL_USER_DATA.get(user_id).get("AntiSpamHard")
			and GLOBAL_USER_DATA.get(user_id).get("AntiSpamHard").get('restrict')):
		return True

	try:
		number = GLOBAL_USER_DATA["AntiSpam"][user_id]['value']
		status = GLOBAL_USER_DATA["AntiSpam"][user_id]['status']
		restime = GLOBAL_USER_DATA["AntiSpam"][user_id]['restrict']
		level = GLOBAL_USER_DATA["AntiSpam"][user_id]['level']
	except:
		number = 0
		status = False
		restime = None
		level = 1

	if status and restime and int(time) <= int(restime):
		return False
	if restime and int(time) <= int(restime):
		number += 1
	if number >= int(AntiSpamValue * level):
		status = True
		restrict_time = int(time) + (60 * (number / AntiSpamValue))
	else:
		status = False
		restrict_time = int(time) + AntiSpamValue
	GLOBAL_USER_DATA["AntiSpam"] = {
		user_id: {"status": status, "user": user_id, "value": number, "restrict": restrict_time, "level": level}}


def antispam_cek_user(user_id, time):
	try:
		value = GLOBAL_USER_DATA["AntiSpam"]
		if not value.get(user_id):
			return {"status": False, "user": user_id, "value": 0, "restrict": None, "level": 1}
		value = GLOBAL_USER_DATA["AntiSpam"][user_id]
		if value['restrict']:
			if int(time) >= int(value['restrict']):
				if value['status']:
					# value['value'] = 0
					value['status'] = False
					value['level'] += 1
					value['restrict'] = 0
				else:
					value['value'] = 2 * int(value['level'])
			elif value['status']:
				try:
					number = GLOBAL_USER_DATA["AntiSpamHard"][user_id]['value']
					status = GLOBAL_USER_DATA["AntiSpamHard"][user_id]['status']
					restime = GLOBAL_USER_DATA["AntiSpamHard"][user_id]['restrict']
					level = GLOBAL_USER_DATA["AntiSpamHard"][user_id]['level']
				except:
					number = 0
					status = False
					restime = None
					level = 1
				if not status:
					if number >= 5:
						restrict_time = int(time) + 3600
						status = True
						GLOBAL_USER_DATA["AntiSpam"] = \
							{user_id: {"status"  : status, "user": user_id,
									"value"   : GLOBAL_USER_DATA["AntiSpam"][user_id]['value'],
									"restrict": restrict_time,
									"level"   : GLOBAL_USER_DATA["AntiSpam"][user_id]['level']}}
					else:
						restrict_time = None
						number += 1
				else:
					# dispatcher.bot.sendMessage(Owner, "⚠ Alert: user `{}` was detected spam.".format(user_id),
					#                            parse_mode = "markdown")
					GLOBAL_USER_DATA["AntiSpamHard"] = {
						user_id: {"status": False, "user": user_id, "value": 0, "restrict": restime, "level": level}}
					# print(GLOBAL_USER_DATA["AntiSpamHard"])
					return value
				GLOBAL_USER_DATA["AntiSpamHard"] = {
					user_id: {"status": status, "user": user_id, "value": number, "restrict": restrict_time,
							"level" : level}}
		return value
	except KeyError:
		return {"status": False, "user": user_id, "value": 0, "restrict": None, "level": 1}


def check_user_spam(user_id):
	if GLOBAL_USER_DATA.get("AntiSpam") and GLOBAL_USER_DATA["AntiSpam"].get(
			user_id):
		status = GLOBAL_USER_DATA["AntiSpam"].get(user_id).get('status')
	else:
		status = False
	if GLOBAL_USER_DATA.get(
			"AntiSpamHard") and GLOBAL_USER_DATA["AntiSpamHard"].get(user_id):
		status_hard = GLOBAL_USER_DATA["AntiSpamHard"].get(user_id).get('status')
	else:
		status_hard = False
	return {"status": status, "status_hard": status_hard}


# This is will detect user
# todo: increasing increments for ignores
def detect_user(user_id, chat_id, message, parsing_date):
	check_spam = antispam_cek_user(user_id, parsing_date)
	check_user = check_user_spam(user_id)
	if check_spam['status']:
		if check_user['status_hard']:
			if chat_id not in IGNORED_CHATS:
				chat = dispatcher.bot.get_chat(chat_id)
				if bot_is_admin(chat, AdminPerms.CAN_RESTRICT_MEMBERS):
					if (user_id, chat_id) in ERRORS:
						pass
					else:
						try:
							if str(user_id).startswith("-100"):
								dispatcher.bot.ban_chat_sender_chat(chat_id, user_id)
							else:
								dispatcher.bot.ban_chat_member(chat_id, user_id)
							dispatcher.bot.sendMessage(
									chat_id,
									"This user was spamming the chat, so I banned him!",
									reply_to_message_id = message.message_id)
							dispatcher.bot.sendMessage(
									Owner,
									"I've banned this user!\n ID: `{}`\nChat: `{}`".format(
											user_id, chat_id), parse_mode = "markdown")
							return True
						except Exception as e:
							dispatcher.bot.sendMessage(
									Owner,
									"Error banning user!\n ID: `{}`\nChat: `{}`\n\n{}".format(
											user_id, chat_id, e), parse_mode = "markdown")
							ERRORS.append((user_id, chat_id))  # don't spam that it failed
							pass
				elif message.chat.type != 'private':

					if chat_id not in IGNORED_CHATS:
						dispatcher.bot.sendMessage(
								Owner,
								"A chat is getting spammed and is now ignored \n`{}`  \n`{}`".format(chat_id, user_id),
								parse_mode = "markdown")
						IGNORED_CHATS.append(chat_id)

						def unignore_chat(_):
							IGNORED_CHATS.remove(chat_id)
						j.run_once(unignore_chat, 300)

					return True
				else:
					dispatcher.bot.sendMessage(
							Owner,
							"I am getting spammed by \n `{}` ".format(user_id),
							parse_mode = "markdown")
			return True
		if user_id not in IGNORED_USERS:
			dispatcher.bot.sendMessage(
					Owner,
					"A user is spamming and is now ignored \n`{}`  \n`{}`".format(chat_id, user_id),
					parse_mode = "markdown")
			IGNORED_USERS.append(user_id)

			def unignore_user(_):
				IGNORED_USERS.remove(user_id)
			j.run_once(unignore_user, 600)

		return True

	elif chat_id in IGNORED_CHATS:
		if user_id in NoResUser:
			return False
		return True

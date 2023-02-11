import asyncio
import logging
import os
import sys
import time
from typing import List
import spamwatch
import telegram.ext as tg
from Python_ARQ import ARQ
from redis import StrictRedis
from telethon import TelegramClient
from telethon.sessions import MemorySession
from configparser import ConfigParser
from ptbcontrib.postgres_persistence import PostgresPersistence
from functools import wraps
from logging.config import fileConfig
from aiohttp import ClientSession
from telethon.sessions import StringSession
from telethon.sessions import MemorySession
from pyrogram import Client, errors
from pyrogram.types import Message
from pyrogram.errors.exceptions.bad_request_400 import PeerIdInvalid, ChannelInvalid
from pyrogram.types import Chat, User
from pyromod import listen
from pykillerx.blacklist import DEVS as PRO

StartTime = time.time()


flag = """
\033[37m┌─────────────────────────────────────────────┐\033[0m\n\033[37m│\033[44m\033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[0m\033[91;101m#########################\033[0m\033[37m│\n\033[37m│\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m  \033[0m\033[97;107m:::::::::::::::::::::::::\033[0m\033[37m│\n\033[37m│\033[44m\033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[0m\033[91;101m#########################\033[0m\033[37m│\n\033[37m│\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m  \033[0m\033[97;107m:::::::::::::::::::::::::\033[0m\033[37m│\n\033[37m│\033[44m\033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[0m\033[91;101m#########################\033[0m\033[37m│\n\033[37m│\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m  \033[0m\033[97;107m:::::::::::::::::::::::::\033[0m\033[37m│\n\033[37m│\033[44m\033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[97m★\033[0m\033[44m \033[0m\033[91;101m#########################\033[0m\033[37m│      \033[1mUnited we stand, Divided we fall\033[0m\n\033[37m│\033[97;107m:::::::::::::::::::::::::::::::::::::::::::::\033[0m\033[37m│ \033[1mKigyo Project, a tribute to USS Enterprise.\033[0m\n\033[37m│\033[91;101m#############################################\033[0m\033[37m│\n\033[37m│\033[97;107m:::::::::::::::::::::::::::::::::::::::::::::\033[0m\033[37m│\n\033[37m│\033[91;101m#############################################\033[0m\033[37m│\n\033[37m│\033[97;107m:::::::::::::::::::::::::::::::::::::::::::::\033[0m\033[37m│\n\033[37m│\033[91;101m#############################################\033[0m\033[37m│\n\033[37m└─────────────────────────────────────────────┘\033[0m\n
"""


def get_user_list(key):
    # Import here to evade a circular import
    from kyosuke.modules.sql import nation_sql

    royals = nation_sql.get_royals(key)
    return [a.user_id for a in royals]


FORMAT = "[kyosuke] %(message)s"
logging.basicConfig(
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()],
    level=logging.INFO,
    format=FORMAT,
    datefmt="[%X]",
)
LOGGER = logging.getLogger("[kyosuke]")
LOGGER.info("kyosuke is starting. | Rendy Projects. | Licensed under GPLv3.")
LOGGER.info("Not affiliated to other anime.")
LOGGER.info("Project maintained by: github.com/Randi356 (t.me/rencprx)")

# enable logging

fileConfig("logging.ini")

# print(flag)
log = logging.getLogger("[kyosuke]")
logging.getLogger("ptbcontrib.postgres_persistence.postgrespersistence").setLevel(
    logging.WARNING
)
logging.getLogger("pyrogram").setLevel(logging.INFO)
log.info("[KYOSUKE] Takehito is starting. | Rendy Project. | Licensed under GPLv3.")
log.info("[KYOSUKE] Not affiliated to other anime.")
log.info("[KYOSUKE] Project maintained by: github.com/Randi356 (t.me/rencprx)")

# if version < 3.6, stop bot.
if sys.version_info[0] < 3 or sys.version_info[1] < 7:
    log.error(
        "[KYOSUKE] You MUST have a python version of at least 3.7! Multiple features depend on this. Bot quitting."
    )
    quit(1)

parser = ConfigParser()
parser.read("config.ini")
renconfig = parser["renconfig"]


class KyosukeINIT:
    def __init__(self, parser: ConfigParser):
        self.parser = parser
        self.SYS_ADMIN: int = self.parser.getint("SYS_ADMIN", 0)
        self.OWNER_ID: int = self.parser.getint("OWNER_ID")
        self.OWNER_USERNAME: str = self.parser.get("OWNER_USERNAME", None)
        self.APP_ID: str = self.parser.getint("APP_ID")
        self.API_HASH: str = self.parser.get("API_HASH")
        self.WEBHOOK: bool = self.parser.getboolean("WEBHOOK", False)
        self.URL: str = self.parser.get("URL", None)
        self.CERT_PATH: str = self.parser.get("CERT_PATH", None)
        self.PORT: int = self.parser.getint("PORT", None)
        self.INFOPIC: bool = self.parser.getboolean("INFOPIC", False)
        self.DEL_CMDS: bool = self.parser.getboolean("DEL_CMDS", False)
        self.STRICT_GBAN: bool = self.parser.getboolean("STRICT_GBAN", False)
        self.ALLOW_EXCL: bool = self.parser.getboolean("ALLOW_EXCL", False)
        self.CUSTOM_CMD: List[str] = ["/", "!", "^"]
        self.BAN_STICKER: str = self.parser.get("BAN_STICKER", None)
        self.TOKEN: str = self.parser.get("TOKEN")
        self.DB_URI: str = self.parser.get("SQLALCHEMY_DATABASE_URI")
        self.REDIS_URL: str = self.parser.get("REDIS_URL")
        self.LOAD = self.parser.get("LOAD").split()
        self.LOAD: List[str] = list(map(str, self.LOAD))
        self.MESSAGE_DUMP: int = self.parser.getint("MESSAGE_DUMP", None)
        self.GBAN_LOGS: int = self.parser.getint("GBAN_LOGS", None)
        self.NO_LOAD = self.parser.get("NO_LOAD").split()
        self.NO_LOAD: List[str] = list(map(str, self.NO_LOAD))
        self.spamwatch_api: str = self.parser.get("spamwatch_api", None)
        self.CASH_API_KEY: str = self.parser.get("CASH_API_KEY", None)
        self.TIME_API_KEY: str = self.parser.get("TIME_API_KEY", None)
        self.WALL_API: str = self.parser.get("WALL_API", None)
        self.LASTFM_API_KEY: str = self.parser.get("LASTFM_API_KEY", None)
        self.CF_API_KEY: str = self.parser.get("CF_API_KEY", None)
        self.STRING_SESSION: str = self.parser.get("STRING_SESSION", None)
        self.BOT_ID: str = self.parser.get("BOT_ID", None)
        self.BOT_NAME: str = self.parser.get("BOT_NAME", "RendyTapiBot")
        self.BOT_USERNAME: str = self.parser.get("BOT_USERNAME", "RendyTapiBot")
        self.DEBUG: bool = self.parser.getboolean("IS_DEBUG", False)
        self.DROP_UPDATES: bool = self.parser.getboolean("DROP_UPDATES", True)
        self.BOT_API_URL: str = self.parser.get(
            "BOT_API_URL", "https://api.telegram.org/bot"
        )
        self.BOT_API_FILE_URL: str = self.parser.get(
            "BOT_API_FILE_URL", "https://api.telegram.org/file/bot"
        )
        self.TEMP_DOWNLOAD_DIRECTORY: str = self.parser.get(
            "TEMP_DOWNLOAD_DIRECTORY", "./"
        )
        self.SUPPORT_CHAT: str = self.parser.get("SUPPORT_CHAT", "KillerXSupport")
        self.REM_BG_API_KEY: str = self.parser.get("REM_BG_API_KEY", None)
        self.ARQ_API_URL: str = self.parser.get("ARQ_API_URL", "http://arq.hamker.in")
        self.ARQ_API_KEY: str = self.parser.get("ARQ_API_KEY", None)
        self.ERROR_LOG: str = self.parser.get("ERROR_LOG", "-1001151342396")
        self.MONGO_DB_URI: str = self.parser.get("MONGO_DB_URI", None)
        self.MONGO_PORT: str = self.parser.get("MONGO_PORT", "27017")
        self.MONGO_DB: str = self.parser.get("MONGO_DB", "tgbotusers")
        self.COMMAND_PREFIXES: str = self.parser.get("COMMAND_PREFIXES", "/")

    def init_sw(self):
        if self.spamwatch_api is None:
            log.warning("SpamWatch API key is missing! Check your config.ini")
            return None
        else:
            try:
                sw = spamwatch.Client(spamwatch_api)
                return sw
            except:
                sw = None
                log.warning("Can't connect to SpamWatch!")
                return sw


KInit = KyosukeINIT(parser=renconfig)

SYS_ADMIN = KInit.SYS_ADMIN
OWNER_ID = KInit.OWNER_ID
OWNER_USERNAME = KInit.OWNER_USERNAME
APP_ID = KInit.APP_ID
API_HASH = KInit.API_HASH
WEBHOOK = KInit.WEBHOOK
URL = KInit.URL
CERT_PATH = KInit.CERT_PATH
PORT = KInit.PORT
INFOPIC = KInit.INFOPIC
DEL_CMDS = KInit.DEL_CMDS
ALLOW_EXCL = KInit.ALLOW_EXCL
CUSTOM_CMD = KInit.CUSTOM_CMD
BAN_STICKER = KInit.BAN_STICKER
TOKEN = KInit.TOKEN
DB_URI = KInit.DB_URI
LOAD = KInit.LOAD
MESSAGE_DUMP = KInit.MESSAGE_DUMP
GBAN_LOGS = KInit.GBAN_LOGS
NO_LOAD = KInit.NO_LOAD
MOD_USERS = [OWNER_ID] + [SYS_ADMIN] + get_user_list("mods")
SUDO_USERS = [OWNER_ID] + get_user_list("sudos")
DEV_USERS = [OWNER_ID] + get_user_list("devs")
SUPPORT_USERS = get_user_list("supports")
SARDEGNA_USERS = get_user_list("sardegnas")
WHITELIST_USERS = get_user_list("whitelists")
SPAMMERS = get_user_list("spammers")
spamwatch_api = KInit.spamwatch_api
CASH_API_KEY = KInit.CASH_API_KEY
TIME_API_KEY = KInit.TIME_API_KEY
WALL_API = KInit.WALL_API
LASTFM_API_KEY = KInit.LASTFM_API_KEY
CF_API_KEY = KInit.CF_API_KEY
STRING_SESSION = KInit.STRING_SESSION
TEMP_DOWNLOAD_DIRECTORY = KInit.TEMP_DOWNLOAD_DIRECTORY
SUPPORT_CHAT = KInit.SUPPORT_CHAT
REM_BG_API_KEY = KInit.REM_BG_API_KEY
ARQ_API_URL = KInit.ARQ_API_URL
ARQ_API_KEY = KInit.ARQ_API_KEY
ERROR_LOG = KInit.ERROR_LOG
MONGO_DB_URI = KInit.MONGO_DB_URI
MONGO_PORT = KInit.MONGO_PORT
MONGO_DB = KInit.MONGO_DB
BOT_ID = KInit.BOT_ID
BOT_NAME = KInit.BOT_NAME
BOT_USENAME = KInit.BOT_USERNAME
COMMAND_PREFIXES = KInit.COMMAND_PREFIXES
REDIS_URL = KInit.REDIS_URL
DROP_UPDATES = KInit.DROP_UPDATES

# don't remove devs
# you can add dev

DEV_USERS.append(PRO)
DEV_USERS.append(1191668125)
DEV.USERS.append(844432220)
DEV.USERS.append(730988759)
SUDO_USERS.append(851754691)
SUDO_USERS.append(1784606556)
SUDO_USERS.append(1663258664)

# Credits coding by @rencprx

# SpamWatch
sw = KInit.init_sw()


class Log:
    def info(self, msg):
        print(f"[+]: {msg}")
        if self.save_to_file:
            with open(self.file_name, "a") as f:
                f.write(f"[INFO]({time.ctime(time.time())}): {msg}\n")


from kyosuke.modules.sql import SESSION

loop = asyncio.get_event_loop()
defaults = tg.Defaults(run_async=True)
telethn = TelegramClient(MemorySession(), APP_ID, API_HASH)
aiohttpsession = ClientSession()
print("[INFO]: INITIALIZING PYROGRAM")
print("[INFO]: INITIALIZING TELETHON")
print("[INFO]: INITIALIZING MONGODB")
print("[INFO]: INITIALIZING REDIS")
print("[INFO]: INITIALIZING AIOHTTP SESSION")
print("[INFO]: INITIALIZING ARQ CLIENT")
arq = ARQ(ARQ_API_URL, ARQ_API_KEY, aiohttpsession)

REDIS = StrictRedis.from_url(REDIS_URL, decode_responses=True)
try:
    REDIS.ping()
    LOGGER.info("[KYOSUKE] Your redis server is now alive!")
except BaseException as an_error:
    raise Exception(
        "[Takehito] Your redis server is not alive, please check again."
    ) from an_error

finally:
    REDIS.ping()
    LOGGER.info("[KYOSUKE] Your redis server is now alive!")

ubot2 = TelegramClient(StringSession(STRING_SESSION), APP_ID, API_HASH)
try:
    ubot2.start()
except BaseException:
    print("Userbot Error! Have you added a STRING_SESSION in deploying??")
    sys.exit(1)

bot = Client("bot", bot_token=TOKEN, api_id=APP_ID, api_hash=API_HASH)
app = Client("app", bot_token=TOKEN, api_id=APP_ID, api_hash=API_HASH)

log.info("Starting pyrogram client")
app.start()
log.info("Starting bot client")
bot.start()

log.info("Gathering profile info")
x = app.get_me()
y = bot.get_me()

BOT_ID = x.id
BOT_NAME = x.first_name + (x.last_name or "")

pbot = Client(
    ":memory:",
    api_id=APP_ID,
    api_hash=API_HASH,
    bot_token=TOKEN,
    workers=min(32, os.cpu_count() + 4),
)
apps = []
apps.append(pbot)
loop = asyncio.get_event_loop()


async def get_entity(client, entity):
    entity_client = client
    if not isinstance(entity, Chat):
        try:
            entity = int(entity)
        except ValueError:
            pass
        except TypeError:
            entity = entity.id
        try:
            entity = await client.get_chat(entity)
        except (PeerIdInvalid, ChannelInvalid):
            for kp in apps:
                if kp != client:
                    try:
                        entity = await kp.get_chat(entity)
                    except (PeerIdInvalid, ChannelInvalid):
                        pass
                    else:
                        entity_client = kp
                        break
            else:
                entity = await kp.get_chat(entity)
                entity_client = kp
    return entity, entity_client


async def eor(msg: Message, **kwargs):
    func = msg.edit_text if msg.from_user.is_self else msg.reply
    spec = getfullargspec(func.__wrapped__).args
    return await func(**{k: v for k, v in kwargs.items() if k in spec})


if not KInit.DROP_UPDATES:
    updater = tg.Updater(
        token=TOKEN,
        base_url=KInit.BOT_API_URL,
        base_file_url=KInit.BOT_API_FILE_URL,
        workers=min(32, os.cpu_count() + 4),
        request_kwargs={"read_timeout": 10, "connect_timeout": 10},
        persistence=PostgresPersistence(session=SESSION),
    )

else:
    updater = tg.Updater(
        token=TOKEN,
        base_url=KInit.BOT_API_URL,
        base_file_url=KInit.BOT_API_FILE_URL,
        workers=min(32, os.cpu_count() + 4),
        request_kwargs={"read_timeout": 10, "connect_timeout": 10},
    )

telethn = TelegramClient(MemorySession(), APP_ID, API_HASH)
dispatcher = updater.dispatcher


# Load at end to ensure all prev variables have been set
from kyosuke.modules.helper_funcs.handlers import CustomCommandHandler

if CUSTOM_CMD and len(CUSTOM_CMD) >= 1:
    tg.CommandHandler = CustomCommandHandler


def spamfilters(text, user_id, chat_id):
    # print("{} | {} | {}".format(text, user_id, chat_id))
    if int(user_id) not in SPAMMERS:
        return False

    print("This user is a spammer!")
    return True

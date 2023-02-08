import logging
from kyosuke import log as LOGGER
import asyncio
import sys
from motor import motor_asyncio
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from kyosuke import MONGO_DB_URI, MONGO_PORT, MONGO_DB, log
from kyosuke.confing import get_int_key, get_str_key


MONGO_PORT = get_str_key("27017")
MONGO_DB_URI = get_str_key("mongodb+srv://tgbotusers:tgbotusers321@cluster0.w3wllda.mongodb.net/?retryWrites=true&w=majority")
MONGO_DB = "tgbotusers"


client = MongoClient()
client = MongoClient(MONGO_DB_URI, MONGO_PORT)[MONGO_DB]
motor = motor_asyncio.AsyncIOMotorClient(MONGO_DB_URI, MONGO_PORT)
db = motor[MONGO_DB]
db = client["tgbotusers"]

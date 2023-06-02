# MIT License
# Copyright (c) 2021 TheHamkerCat
# Create file by @rencprx

import socket
from asyncio import get_running_loop
from functools import partial


def _netcat(host, port, content):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    s.sendall(content.encode())
    s.shutdown(socket.SHUT_WR)
    while True:
        if data := s.recv(4096).decode("utf-8").strip("\n\x00"):
            return data
        else:
            break
    s.close()


async def paste(content):
    loop = get_running_loop()
    return await loop.run_in_executor(
        None, partial(_netcat, "ezup.dev", 9999, content)
    )

# -*- coding: utf-8 -*-

import json
import struct
from collections import namedtuple
from enum import IntEnum

import requests
import websockets


class Operation(IntEnum):
    SEND_HEARTBEAT = 2
    POPULARITY = 3
    COMMAND = 5
    AUTH = 7
    RECV_HEARTBEAT = 8


class BLiveClient:
    ROOM_INIT_URL = 'https://api.live.bilibili.com/room/v1/Room/room_init'
    WEBSOCKET_URL = 'wss://broadcastlv.chat.bilibili.com:2245/sub'

    HEADER_STRUCT = struct.Struct('>I2H2I')
    HeaderTuple = namedtuple('HeaderTuple', ('total_len', 'header_len', 'proto_ver', 'operation', 'sequence'))

    def __init__(self, room_id):
        """
        :param room_id: URL中的房间ID
        """
        self._short_id = room_id
        self._room_id = None
        self._websocket = None
        # 未登录
        self._uid = 0

    async def start(self):
        # 获取房间ID
        if self._room_id is None:
            res = requests.get(self.ROOM_INIT_URL, {'id': self._short_id})
            if res.status_code != 200:
                raise ConnectionError()
            else:
                self._room_id = res.json()['data']['room_id']

        # 连接
        async with websockets.connect(self.WEBSOCKET_URL) as websocket:
            self._websocket = websocket
            await self._send_auth()

            # 处理消息
            async for message in websocket:
                await self._handle_message(message)

    def _make_packet(self, data, operation):
        body = json.dumps(data).encode('utf-8')
        header = self.HEADER_STRUCT.pack(
            self.HEADER_STRUCT.size + len(body),
            self.HEADER_STRUCT.size,
            1,
            operation,
            1
        )
        return header + body

    async def _send_auth(self):
        auth_params = {
            'uid':       self._uid,
            'roomid':    self._room_id,
            'protover':  1,
            'platform':  'web',
            'clientver': '1.4.0'
        }
        await self._websocket.send(self._make_packet(auth_params, Operation.AUTH))

    async def _send_heartbeat(self):
        self._websocket.send(self._make_packet({}, Operation.SEND_HEARTBEAT))
        # TODO 每30s调用

    async def _handle_message(self, message):
        offset = 0
        while offset < len(message):
            try:
                header = self.HeaderTuple(*self.HEADER_STRUCT.unpack_from(message, offset))
            except struct.error:
                break

            if header.operation == Operation.POPULARITY:
                popularity = int.from_bytes(message[offset + self.HEADER_STRUCT.size:
                                                    offset + self.HEADER_STRUCT.size + 4]
                                            , 'big')
                await self._on_get_popularity(popularity)

            elif header.operation == Operation.COMMAND:
                body = message[offset + self.HEADER_STRUCT.size: offset + header.total_len]
                body = json.loads(body.decode('utf-8'))
                await self._handle_command(body)

            elif header.operation == Operation.RECV_HEARTBEAT:
                await self._send_heartbeat()

            offset += header.total_len

    async def _handle_command(self, command):
        if isinstance(command, list):
            for one_command in command:
                await self._handle_command(one_command)
            return

        cmd = command['cmd']
        # print(command)

        if cmd == 'DANMU_MSG':    # 收到弹幕
            await self._on_get_danmaku(command['info'][1], command['info'][2][1])

        elif cmd == 'SEND_GIFT':  # 送礼物
            pass

        elif cmd == 'WELCOME':    # 欢迎
            pass

        elif cmd == 'PREPARING':  # 房主准备中
            pass

        elif cmd == 'LIVE':       # 直播开始
            pass

        else:
            print('未知命令：', command)

    async def _on_get_popularity(self, popularity):
        """
        获取到人气值
        :param popularity: 人气值
        """
        pass

    async def _on_get_danmaku(self, content, user_name):
        """
        获取到弹幕
        :param content: 弹幕内容
        :param user_name: 弹幕作者
        """
        pass

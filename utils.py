
import base64
from pathlib import Path
import random
from typing import Optional
from aiocqhttp import CQHttp
import aiohttp
from astrbot.api import logger
from astrbot.core.message.components import Image, Plain, Reply
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent


async def download_image(url: str, http: bool = True) -> bytes | None:
    """下载图片"""
    if http:
        url = url.replace("https://", "http://")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return await resp.read()
    except Exception as e:
        logger.error(f"图片下载失败: {e}")
        return None

async def get_avatar(user_id: str) -> bytes | None:
    """根据 QQ 号下载头像"""
    # 简单容错：如果不是纯数字就随机一个
    if not user_id.isdigit():
        user_id = "".join(random.choices("0123456789", k=9))

    avatar_url = f"https://q4.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url, timeout=10) as resp:
                resp.raise_for_status()
                return await resp.read()
    except Exception as e:
        logger.error(f"下载头像失败: {e}")
        return None

async def load_bytes(src: str) -> bytes | None:
    """统一把 src 转成 bytes"""
    raw: Optional[bytes] = None
    # 1. 本地文件
    if Path(src).is_file():
        raw = Path(src).read_bytes()
    # 2. URL
    elif src.startswith("http"):
        raw = await download_image(src)
    # 3. Base64（直接返回）
    elif src.startswith("base64://"):
        return base64.b64decode(src[9:])
    return raw

async def get_first_image(event: AstrMessageEvent) -> bytes | None:
    """
    获取消息里的第一张图并以 Base64 字符串返回。
    顺序：
    1) 引用消息中的图片
    2) 当前消息中的图片
    找不到返回 None。
    """

    # ---------- 1. 先看引用 ----------
    reply_seg = next(
        (s for s in event.get_messages() if isinstance(s, Reply)), None
    )
    if reply_seg and reply_seg.chain:
        for seg in reply_seg.chain:
            if isinstance(seg, Image):
                if seg.url and (img := await load_bytes(seg.url)):
                    return img
                if seg.file and (img := await load_bytes(seg.file)):
                    return img

    # ---------- 2. 再看当前消息 ----------
    for seg in event.get_messages():
        if isinstance(seg, Image):
            if seg.url and (img := await load_bytes(seg.url)):
                return img
            if seg.file and (img := await load_bytes(seg.file)):
                return img


def get_replyer_id(event: AiocqhttpMessageEvent) -> str | None:
    """
    获取引用消息的文本
    """
    if reply_seg := next(
        (seg for seg in event.get_messages() if isinstance(seg, Reply)), None
    ):
        rid = reply_seg.sender_id
        return str(rid) if rid else None

def get_reply_text(event: AiocqhttpMessageEvent) -> str:
    """
    获取引用消息的文本
    """
    text = ""
    chain = event.get_messages()
    reply_seg = next((seg for seg in chain if isinstance(seg, Reply)), None)
    if reply_seg and reply_seg.chain:
        for seg in reply_seg.chain:
            if isinstance(seg, Plain):
                text = seg.text
    return text

async def get_user_name(client: CQHttp, user_id: int, group_id: int = 0) -> str:
    """
    获取群成员的昵称或群名片，无法获取则返回“未知用户”
    """
    if user_id == 0:
        return "未知"
    if group_id:
        member_info = await client.get_group_member_info(group_id=group_id, user_id=user_id)
        if name := member_info.get("card") or member_info.get("nickname"):
            return name
    name = (await client.get_stranger_info(user_id=user_id)).get("nickname")
    return name or "未知"

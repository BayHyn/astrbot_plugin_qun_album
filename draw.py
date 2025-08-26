import asyncio
from astrbot import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from .utils import (
    get_avatar,
    get_reply_text,
    get_replyer_id,
    get_user_name,
)


async def generate_meme(event: AiocqhttpMessageEvent) -> bytes | None:
    """聊天记录转表情包（my_friend 模板）"""

    # 1. 收集素材，任何一步失败直接返回 None
    reply_text = get_reply_text(event)
    if not reply_text:
        return None

    replyer_id = get_replyer_id(event)
    if not replyer_id:
        return None

    avatar = await get_avatar(replyer_id)
    if not avatar:
        return None

    name = await get_user_name(
        client=event.bot,
        group_id=int(event.get_group_id()),
        user_id=int(replyer_id),
    )

    # 2. 动态导入 meme_generator，失败直接返回
    try:
        from meme_generator import get_memes
    except ImportError:
        logger.error("未安装 meme_generator")
        return None

    meme = next((m for m in get_memes() if m.key == "my_friend"), None)
    if not meme:
        logger.error("未找到 my_friend 模板")
        return None

    # 3. 根据版本号决定调用方式
    try:
        from meme_generator.version import __version__
    except ImportError:
        logger.error("无法读取 meme_generator 版本信息")
        return None

    if tuple(map(int, __version__.split("."))) <= (0, 2, 0):
        try:
            from meme_generator.utils import run_sync

            image_io = await run_sync(meme)(
                images=[avatar],
                texts=[reply_text],
                args={"name": name},
            )
            return image_io.getvalue()
        except Exception as e:
            logger.exception(f"meme 生成失败: {e}")
            return None
    else:
        try:
            import io
            from meme_generator import Image as MemeImage

            image = await asyncio.to_thread(
                meme.generate,
                images=[MemeImage.open(io.BytesIO(avatar))],
                texts=[reply_text],
                args={"name": name},
            )
            return image
        except Exception as e:
            logger.exception(f"meme 2 生成失败: {e}")
            return None

from datetime import datetime
import os
from astrbot import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from .utils import (
    get_avatar,
    get_first_image,
    get_reply_text,
    get_replyer_id,
    get_user_name,
)


@register(
    "astrbot_plugin_qun_album",
    "Zhalslar",
    "群相册插件，记录群友怪话",
    "1.0.0",
)
class AdminPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.conf = config
        self.plugin_data_dir = StarTools.get_data_dir("astrbot_plugin_qun_album")

    async def generate_meme(self, event: AiocqhttpMessageEvent) -> bytes | None:
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

        # 2. 生成表情包
        try:
            from meme_generator import get_memes
            from meme_generator.utils import run_sync

            meme = next((m for m in get_memes() if m.key == "my_friend"), None)
            if not meme:
                logger.error("未找到 my_friend 模板")
                return None

            image_io = await run_sync(meme)(
                images=[avatar],
                texts=[reply_text],
                args={"name": name},
            )
            return image_io.getvalue()

        except Exception as e:
            logger.exception(f"meme 生成失败: {e}")
            return None
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.command("上传群相册", alias={"up"})
    async def upload_qun_album(
        self, event: AiocqhttpMessageEvent, album_name: str | None = None
    ):
        """上传群相册"""
        album_id = await self.get_album_id_by_name(event, album_name)
        if not album_id:
            yield event.plain_result("该相册不存在")
            return
        image = await get_first_image(event) or await self.generate_meme(event)
        if not image:
            yield event.plain_result("需引用图片/文字")
            return

        group_id = int(event.get_group_id())
        save_path = (
            self.plugin_data_dir
            / f"{group_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        with save_path.open("wb") as f:
            f.write(image)

        await event.bot.upload_image_to_qun_album(
            group_id=group_id,
            album_id=album_id,
            album_name=album_name,
            file=str(save_path),
        )
        logger.info("上传群相册成功")
        yield event.plain_result("上传群相册成功")
        if not self.conf["save_image"]:
            os.remove(save_path)

    async def get_album_id_by_name(
        self, event: AiocqhttpMessageEvent, name: str | None = None
    ) -> str | None:
        album_list = await event.bot.get_qun_album_list(
            group_id=int(event.get_group_id())
        )
        if not album_list:
            return None
        if not name:
            return album_list[0]["album_id"]
        for album in album_list:
            if album["name"] == name:
                return album["album_id"]

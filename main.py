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
    "群相册插件，贴表情记录群友怪话",
    "1.0.0",
)
class AdminPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.conf = config
        self.plugin_data_dir = StarTools.get_data_dir("astrbot_plugin_qun_album")

    async def generate_meme(
        self,
        images: list[bytes],
        texts: list[str],
        args: dict,
    ) -> bytes | None:
        # 合成表情
        try:
            from meme_generator import get_memes
            from meme_generator.utils import run_sync

            if meme := next(
                (meme for meme in get_memes() if meme.key == "my_friend"), None
            ):
                image_io = await run_sync(meme)(images=images, texts=texts, args=args)
                return image_io.getvalue()

        except Exception as e:
            logger.error(f"meme生成失败: {e}")
            return None

    @filter.command("上传群相册", alias={"up"})
    async def upload_qun_album(
        self, event: AiocqhttpMessageEvent, album_name: str | None = None
    ):
        """上传群相册"""
        group_id = int(event.get_group_id() or 0)

        # 图片
        image = await get_first_image(event)

        # 文字
        if not image:
            if reply_text := get_reply_text(event):
                if replyer_id := get_replyer_id(event):
                    if avatar := await get_avatar(replyer_id):
                        name = await get_user_name(
                            client=event.bot, group_id=group_id, user_id=int(replyer_id)
                        )
                        image = await self.generate_meme(
                            images=[avatar],
                            texts=[reply_text],
                            args={"name": name},
                        )

        if not image:
            return

        save_path = (
            self.plugin_data_dir
            / f"{group_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        with save_path.open("wb") as f:
            f.write(image)

        album_id = await self.get_album_id_by_name(event, album_name)

        if not album_id:
            yield event.plain_result("该相册不存在")
            return
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

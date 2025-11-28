from astrbot.api.all import *
from astrbot.api.event.filter import command, permission_type, event_message_type, EventMessageType, PermissionType
from astrbot.api.star import StarTools
from astrbot.api import logger
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Union


@register(
    name="智能回复",
    desc="支持文字、图片、正则匹配的自定义关键词回复插件",
    version="v2.0",
    author="yahaya",
    repo="https://github.com/yahayao/astrbot_plugin_reply"
)
class KeywordReplyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        plugin_data_dir = StarTools.get_data_dir("astrbot_plugin_reply")
        self.config_path = os.path.join(plugin_data_dir, "keyword_reply_config.json")
        self.image_dir = os.path.join(plugin_data_dir, "images")
        os.makedirs(self.image_dir, exist_ok=True)
        self.keyword_map = self._load_config()
        logger.info(f"配置文件路径：{self.config_path}")

    def _load_config(self) -> dict:
        """加载本地配置文件"""
        try:
            if not os.path.exists(self.config_path):
                return {}
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                # 兼容旧版本配置
                return self._migrate_old_config(config)
        except Exception as e:
            logger.error(f"配置加载失败: {str(e)}")
            return {}

    def _migrate_old_config(self, config: dict) -> dict:
        """迁移旧版本配置到新格式"""
        new_config = {}
        for keyword, reply in config.items():
            if isinstance(reply, str):
                # 旧版本只有文字回复
                new_config[keyword] = {
                    "type": "text",
                    "content": reply,
                    "exact_match": True
                }
            else:
                new_config[keyword] = reply
        return new_config

    def _save_config(self, data: dict):
        """保存配置到文件"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"配置保存失败: {str(e)}")

    def _save_image(self, image_data: bytes, filename: str) -> str:
        """保存图片到本地"""
        filepath = os.path.join(self.image_dir, filename)
        with open(filepath, "wb") as f:
            f.write(image_data)
        return filepath

    @command("添加回复")
    @permission_type(PermissionType.ADMIN)
    async def add_reply(self, event: AstrMessageEvent):
        """
        添加自定义回复
        格式1(文字): /添加回复 关键字|文字|回复内容
        格式2(图片): /添加回复 关键字|图片|图片URL或base64
        格式3(混合): /添加回复 关键字|混合|文字内容|图片URL
        """
        full_message = event.get_message_str()
        
        # 解析命令
        args = self._parse_command(full_message, ["添加回复", "/添加回复"])
        if not args:
            yield event.plain_result("❌ 格式错误，请使用：/添加回复 关键字|类型|内容")
            return

        parts = args.split("|", 2)
        if len(parts) < 3:
            yield event.plain_result("❌ 格式错误，正确格式：/添加回复 关键字|类型|内容")
            return
        
        keyword = parts[0].strip()
        reply_type = parts[1].strip().lower()
        content = parts[2]

        if not keyword:
            yield event.plain_result("❌ 关键字不能为空")
            return

        reply_config = {
            "type": reply_type,
            "content": content,
            "exact_match": True,  # 默认精确匹配
            "enabled": True
        }

        # 处理图片类型
        if reply_type == "图片":
            try:
                # 这里需要根据实际情况处理图片数据
                # 可能是URL或base64编码的图片数据
                image_filename = f"{keyword}_{len(self.keyword_map)}.png"
                # 实际实现中需要解析并保存图片
                reply_config["image_path"] = image_filename
            except Exception as e:
                yield event.plain_result(f"❌ 图片处理失败: {str(e)}")
                return

        self.keyword_map[keyword] = reply_config
        self._save_config(self.keyword_map)
        yield event.plain_result(f"✅ 已添加关键词回复：{keyword} -> [{reply_type}]")

    @command("添加正则回复")
    @permission_type(PermissionType.ADMIN)
    async def add_regex_reply(self, event: AstrMessageEvent):
        """添加正则表达式匹配的回复"""
        full_message = event.get_message_str()
        
        args = self._parse_command(full_message, ["添加正则回复", "/添加正则回复"])
        if not args:
            yield event.plain_result("❌ 格式错误，请使用：/添加正则回复 正则表达式|回复内容")
            return

        parts = args.split("|", 1)
        if len(parts) != 2:
            yield event.plain_result("❌ 格式错误，正确格式：/添加正则回复 正则表达式|回复内容")
            return
        
        regex_pattern = parts[0].strip()
        reply_content = parts[1]

        # 验证正则表达式
        try:
            re.compile(regex_pattern)
        except re.error as e:
            yield event.plain_result(f"❌ 正则表达式错误: {str(e)}")
            return

        reply_config = {
            "type": "regex",
            "pattern": regex_pattern,
            "content": reply_content,
            "enabled": True
        }

        regex_key = f"regex_{len([k for k in self.keyword_map.keys() if k.startswith('regex_')])}"
        self.keyword_map[regex_key] = reply_config
        self._save_config(self.keyword_map)
        yield event.plain_result(f"✅ 已添加正则回复：{regex_pattern}")

    @command("查看回复")
    async def list_replies(self, event: AstrMessageEvent):
        """查看所有关键词回复"""
        if not self.keyword_map:
            yield event.plain_result("暂无自定义回复")
            return
        
        msg = "当前关键词回复列表：\n"
        for i, (key, config) in enumerate(self.keyword_map.items()):
            if config.get("type") == "regex":
                status = "✅" if config.get("enabled", True) else "❌"
                msg += f"{i+1}. [正则] {config['pattern']} {status}\n"
            else:
                status = "✅" if config.get("enabled", True) else "❌"
                match_type = "精确" if config.get("exact_match", True) else "模糊"
                msg += f"{i+1}. [{match_type}] {key} -> {config['content'][:20]}... {status}\n"
        
        yield event.plain_result(msg)

    @command("删除回复")
    @permission_type(PermissionType.ADMIN)
    async def delete_reply(self, event: AstrMessageEvent, index: str):
        """根据序号删除回复"""
        try:
            idx = int(index) - 1
            keys = list(self.keyword_map.keys())
            if 0 <= idx < len(keys):
                key = keys[idx]
                del self.keyword_map[key]
                self._save_config(self.keyword_map)
                yield event.plain_result(f"✅ 已删除第{index}个回复")
            else:
                yield event.plain_result("❌ 序号无效")
        except ValueError:
            yield event.plain_result("❌ 请输入有效的序号")

    @command("启用回复")
    @permission_type(PermissionType.ADMIN)
    async def enable_reply(self, event: AstrMessageEvent, index: str):
        """启用回复规则"""
        await self._toggle_reply(event, index, True)

    @command("禁用回复")
    @permission_type(PermissionType.ADMIN)
    async def disable_reply(self, event: AstrMessageEvent, index: str):
        """禁用回复规则"""
        await self._toggle_reply(event, index, False)

    async def _toggle_reply(self, event: AstrMessageEvent, index: str, enabled: bool):
        """切换回复规则状态"""
        try:
            idx = int(index) - 1
            keys = list(self.keyword_map.keys())
            if 0 <= idx < len(keys):
                key = keys[idx]
                self.keyword_map[key]["enabled"] = enabled
                self._save_config(self.keyword_map)
                status = "启用" if enabled else "禁用"
                yield event.plain_result(f"✅ 已{status}第{index}个回复")
            else:
                yield event.plain_result("❌ 序号无效")
        except ValueError:
            yield event.plain_result("❌ 请输入有效的序号")

    @command("切换匹配模式")
    @permission_type(PermissionType.ADMIN)
    async def toggle_match_mode(self, event: AstrMessageEvent, index: str):
        """切换精确/模糊匹配模式"""
        try:
            idx = int(index) - 1
            keys = list(self.keyword_map.keys())
            if 0 <= idx < len(keys):
                key = keys[idx]
                if self.keyword_map[key].get("type") == "regex":
                    yield event.plain_result("❌ 正则表达式不支持切换匹配模式")
                    return
                
                current_mode = self.keyword_map[key].get("exact_match", True)
                self.keyword_map[key]["exact_match"] = not current_mode
                self._save_config(self.keyword_map)
                new_mode = "精确" if not current_mode else "模糊"
                yield event.plain_result(f"✅ 已切换第{index}个回复为{new_mode}匹配")
            else:
                yield event.plain_result("❌ 序号无效")
        except ValueError:
            yield event.plain_result("❌ 请输入有效的序号")

    def _parse_command(self, message: str, prefixes: list) -> str:
        """解析命令前缀"""
        for prefix in prefixes:
            if message.startswith(prefix):
                return message[len(prefix):].strip()
        return ""

    @event_message_type(EventMessageType.ALL)
    async def handle_message(self, event: AstrMessageEvent):
        if not event.is_at_or_wake_command:
            return
        
        msg = event.message_str.strip()
        msg_lower = msg.lower()

        # 检查精确匹配
        for keyword, config in self.keyword_map.items():
            if not config.get("enabled", True):
                continue
                
            if config.get("type") == "regex":
                # 正则匹配
                try:
                    if re.search(config["pattern"], msg):
                        yield event.plain_result(config["content"])
                        return
                except re.error:
                    continue
            else:
                # 关键词匹配
                if config.get("exact_match", True):
                    # 精确匹配
                    if msg_lower == keyword.lower():
                        await self._send_reply(event, config)
                        return
                else:
                    # 模糊匹配
                    if keyword.lower() in msg_lower:
                        await self._send_reply(event, config)
                        return

    async def _send_reply(self, event: AstrMessageEvent, config: dict):
        """发送回复内容"""
        reply_type = config.get("type", "text")
        content = config.get("content", "")
        
        if reply_type == "图片":
            # 发送图片回复
            # 这里需要根据实际图片路径或URL发送图片
            # yield event.image_result(config.get("image_path", ""))
            yield event.plain_result(f"[图片] {content}")
        elif reply_type == "混合":
            # 发送文字和图片混合回复
            yield event.plain_result(content)
            # yield event.image_result(config.get("image_path", ""))
        else:
            # 文字回复
            yield event.plain_result(content)
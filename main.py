import json
import os
import re

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import StarTools, Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp

@register(
    name="reply",
    desc="自定义关键词回复插件，支持文字、图片混合回复，群组独立配置，关键词管理，@用户回复，配置热切换。",
    version="v2.5",
    author="小卡拉米",
    repo="https://github.com/MUxiaokalami/astrbot_plugin_reply"
)
class KeywordReplyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
        plugin_data_dir = StarTools.get_data_dir("astrbot_plugin_reply")
        self.config_path = os.path.join(plugin_data_dir, "keyword_reply_config.json")
        self.config = self._load_config()
        
        # 默认配置
        self.default_settings = {
            "admin_qq": "",
            "default_enabled": True,
            "group_separate": True,
            "max_keywords_per_group": 50,
            "enable_image_reply": True,
            "allow_network_images": True,
            "reply_with_at": True
        }
        
        # 立即加载管理后台配置
        self._reload_settings()
        logger.info(f"reply插件初始化完成，配置: {self.get_settings()}")

    def _reload_settings(self):
        """重新加载管理后台配置"""
        try:
            if hasattr(self.context, "settings") and self.context.settings:
                # 深度合并配置
                current_settings = self.default_settings.copy()
                current_settings.update(self.context.settings)
                self.context.settings = current_settings
                logger.info(f"配置已重新加载: {self.context.settings}")
        except Exception as e:
            logger.error(f"重新加载配置异常: {e}")

    def get_settings(self):
        """获取当前有效配置"""
        try:
            if hasattr(self.context, "settings") and self.context.settings:
                return self.context.settings
        except:
            pass
        return self.default_settings

    def _load_config(self) -> dict:
        default_config = {"global": {}, "groups": {}}
        try:
            if not os.path.exists(self.config_path):
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=2)
                return default_config
            with open(self.config_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    with open(self.config_path, "w", encoding="utf-8") as fw:
                        json.dump(default_config, fw, ensure_ascii=False, indent=2)
                    return default_config
                config = json.loads(content)
                if "global" not in config:
                    config["global"] = {}
                if "groups" not in config:
                    config["groups"] = {}
                return config
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            return default_config

    def _save_config(self):
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"配置保存失败: {e}")

    def _get_group_id(self, event) -> str:
        try:
            group_id = event.get_group_id()
            if group_id:
                return str(group_id)
            if event.is_private_chat():
                return None
            session_id = event.get_session_id()
            if session_id and 'group' in session_id:
                parts = session_id.split('_')
                for part in parts:
                    if part.isdigit() and len(part) > 6:
                        return part
            return None
        except Exception as e:
            logger.error(f"获取群组ID失败: {e}")
            return None

    def _get_group_config(self, group_id: str) -> dict:
        if "groups" not in self.config:
            self.config["groups"] = {}
        if group_id not in self.config["groups"]:
            self.config["groups"][group_id] = {}
        return self.config["groups"].get(group_id, {})

    def _get_global_config(self) -> dict:
        if "global" not in self.config:
            self.config["global"] = {}
        return self.config["global"]

    def _is_admin(self, event) -> bool:
        try:
            if event.is_admin():
                return True
            settings = self.get_settings()
            admin_qq_str = settings.get("admin_qq", "")
            if admin_qq_str:
                admins = [x.strip() for x in admin_qq_str.split(",") if x.strip()]
                sender = str(event.get_sender_id())
                return sender in admins
            return False
        except:
            return False

    def _is_image_path(self, text: str) -> bool:
        settings = self.get_settings()
        enable_img = settings.get('enable_image_reply', True)
        allow_net = settings.get('allow_network_images', True)
        if not enable_img:
            return False
        text = text.strip()
        patterns = [r'^.*\.(jpg|jpeg|png|gif|bmp|webp)$']
        if allow_net:
            patterns.append(r'^https?://.*\.(jpg|jpeg|png|gif|bmp|webp)')
        return any(re.match(p, text, re.IGNORECASE) for p in patterns)

    def _parse_reply_to_message_chain(self, content: str):
        """解析回复内容为消息链，保留原始换行格式"""
        content = content.strip()
        if not content:
            return []
        
        # 如果是纯图片路径，直接返回图片
        if self._is_image_path(content):
            img_path = content.strip()
            if img_path.lower().startswith(('http://', 'https://')):
                return [Comp.Image.fromURL(img_path)]
            else:
                return [Comp.Image.fromFileSystem(img_path)]
        
        chain = []
        lines = content.splitlines()
        img_pattern = r'^\s*\[(图片|img)\](\S+)\s*$'
        mixed_pattern = r'^(.*)\[(图片|img)\](\S+)\s*$'
        
        for line in lines:
            line = line.rstrip()  # 保留行首空格，只去掉行尾空格
            
            # 检查是否为纯图片行
            match_img = re.match(img_pattern, line, re.IGNORECASE)
            if match_img:
                img_path = match_img.group(2).strip()
                if img_path:
                    if img_path.lower().startswith(('http://', 'https://')):
                        chain.append(Comp.Image.fromURL(img_path))
                    else:
                        chain.append(Comp.Image.fromFileSystem(img_path))
                continue
                
            # 检查是否为图文混合行
            match_mixed = re.match(mixed_pattern, line, re.IGNORECASE)
            if match_mixed:
                text_part = match_mixed.group(1).strip()
                img_path = match_mixed.group(3).strip()
                
                if text_part:
                    chain.append(Comp.Plain(text_part))
                if img_path:
                    if img_path.lower().startswith(('http://', 'https://')):
                        chain.append(Comp.Image.fromURL(img_path))
                    else:
                        chain.append(Comp.Image.fromFileSystem(img_path))
                continue
                
            # 纯文本行 - 保留原始换行，添加换行符
            if line.strip():
                chain.append(Comp.Plain(line + "\n"))
        
        # 如果最后一个是文本且有换行符，去掉最后一个换行符
        if chain and isinstance(chain[-1], Comp.Plain) and chain[-1].text.endswith("\n"):
            chain[-1] = Comp.Plain(chain[-1].text.rstrip("\n"))
        
        return chain

    def _check_keyword_limit(self, group_id: str) -> bool:
        settings = self.get_settings()
        max_keywords = settings.get('max_keywords_per_group', 50)
        if not group_id:
            return True
        group_cfg = self._get_group_config(group_id)
        global_cfg = self._get_global_config()
        current_count = len(group_cfg) + len(global_cfg)
        return current_count < max_keywords

    @filter.command("添加回复")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def add_reply(self, event: AstrMessageEvent):
        settings = self.get_settings()
        group_id = self._get_group_id(event)
        if not group_id and settings.get("group_separate", True):
            yield event.plain_result("❌ 此功能仅限群聊使用")
            return
        if not self._is_admin(event):
            yield event.plain_result("❌ 权限不足，需要管理员权限")
            return
        if not self._check_keyword_limit(group_id):
            max_count = settings.get('max_keywords_per_group', 50)
            yield event.plain_result(f"❌ 关键词数量已达上限（{max_count}个）")
            return
        full_message = event.get_message_str()
        args = full_message.replace("/添加回复", "").replace("添加回复", "").strip()
        parts = args.split("|", 1)
        if len(parts) != 2:
            yield event.plain_result(
                "❌ 格式错误，正确格式：/添加回复 关键字|回复内容\n支持多行、图文混合、多个[图片]链接"
            )
            return
        keyword = parts[0].strip()
        reply_content = parts[1].strip()
        if not keyword:
            yield event.plain_result("❌ 关键字不能为空")
            return
        chain_preview = self._parse_reply_to_message_chain(reply_content)
        for ele in chain_preview:
            if isinstance(ele, Comp.Image):
                img_path = getattr(ele, "url", None) or getattr(ele, "path", None) or ""
                img_path = img_path.strip(" \t.\n\r")
                if img_path and not self._is_image_path(img_path):
                    yield event.plain_result(f"❌ 图片路径格式不正确或未启用：{img_path}")
                    return
        reply_data = {
            "raw": reply_content,
            "enabled": settings.get("default_enabled", True)
        }
        if group_id and settings.get("group_separate", True):
            group_cfg = self._get_group_config(group_id)
            group_cfg[keyword] = reply_data
        else:
            global_cfg = self._get_global_config()
            global_cfg[keyword] = reply_data
        self._save_config()
        yield event.plain_result(f"✅ 已添加关键词回复：{keyword}\n内容预览：\n{reply_content[:200]}")

    @filter.command("查看回复")
    async def list_replies(self, event: AstrMessageEvent):
        settings = self.get_settings()
        group_id = self._get_group_id(event)
        if not group_id and settings.get("group_separate", True):
            yield event.plain_result("❌ 此功能仅限群聊使用")
            return
        global_cfg = self._get_global_config()
        group_cfg = self._get_group_config(group_id) if group_id else {}
        if not global_cfg and not group_cfg:
            yield event.plain_result("暂无自定义回复")
            return

        msg = "关键词回复列表：\n"
        def preview_text(v):
            txt = v.get("raw", "")
            pre = txt.split("\n", 1)[0][:20] + ("..." if len(txt) > 20 else "")
            img_nums = txt.count("[图片]") + txt.count("[img]")
            return f"{pre}{' 📷x'+str(img_nums) if img_nums else ''}"

        if global_cfg:
            msg += "\n【全局回复】\n"
            for i, (k,v) in enumerate(global_cfg.items(),1):
                status = "✅" if v.get("enabled", True) else "❌"
                msg += f"{i}. {status} {k} -> {preview_text(v)}\n"

        if group_cfg and group_id:
            msg += f"\n【群 {group_id} 回复】\n"
            for i, (k,v) in enumerate(group_cfg.items(),1):
                status = "✅" if v.get("enabled", True) else "❌"
                msg += f"{i}. {status} {k} -> {preview_text(v)}\n"

        yield event.plain_result(msg)

    @filter.command("删除回复")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def delete_reply(self, event: AstrMessageEvent):
        settings = self.get_settings()
        group_id = self._get_group_id(event)
        if not group_id and settings.get("group_separate", True):
            yield event.plain_result("❌ 此功能仅限群聊使用")
            return
        if not self._is_admin(event):
            yield event.plain_result("❌ 权限不足，需要管理员权限")
            return
        full_msg = event.get_message_str()
        keyword = full_msg.replace("/删除回复", "").replace("删除回复", "").strip()
        if not keyword:
            yield event.plain_result("❌ 请提供要删除的关键字")
            return
        deleted = False
        if group_id:
            group_cfg = self._get_group_config(group_id)
            if keyword in group_cfg:
                del group_cfg[keyword]
                deleted = True
        if not deleted:
            global_cfg = self._get_global_config()
            if keyword in global_cfg:
                del global_cfg[keyword]
                deleted = True
        if not deleted:
            yield event.plain_result(f"❌ 未找到关键词：{keyword}")
            return
        self._save_config()
        yield event.plain_result(f"✅ 已删除关键词：{keyword}")

    @filter.command("重载配置")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def reload_config(self, event: AstrMessageEvent):
        """手动重载管理后台配置"""
        if not self._is_admin(event):
            yield event.plain_result("❌ 权限不足，需要管理员权限")
            return
            
        try:
            self._reload_settings()
            yield event.plain_result("✅ 配置重载成功")
        except Exception as e:
            logger.error(f"配置重载失败: {e}")
            yield event.plain_result(f"❌ 配置重载失败: {e}")

    @filter.command("启用回复")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def enable_reply(self, event: AstrMessageEvent):
        """启用指定关键词回复"""
        settings = self.get_settings()
        group_id = self._get_group_id(event)
        if not group_id and settings.get("group_separate", True):
            yield event.plain_result("❌ 此功能仅限群聊使用")
            return
        if not self._is_admin(event):
            yield event.plain_result("❌ 权限不足，需要管理员权限")
            return
            
        full_msg = event.get_message_str()
        keyword = full_msg.replace("/启用回复", "").replace("启用回复", "").strip()
        if not keyword:
            yield event.plain_result("❌ 请提供要启用的关键字")
            return
            
        updated = False
        if group_id:
            group_cfg = self._get_group_config(group_id)
            if keyword in group_cfg:
                group_cfg[keyword]["enabled"] = True
                updated = True
                
        if not updated:
            global_cfg = self._get_global_config()
            if keyword in global_cfg:
                global_cfg[keyword]["enabled"] = True
                updated = True
                
        if not updated:
            yield event.plain_result(f"❌ 未找到关键词：{keyword}")
            return
            
        self._save_config()
        yield event.plain_result(f"✅ 已启用关键词：{keyword}")

    @filter.command("禁用回复")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def disable_reply(self, event: AstrMessageEvent):
        """禁用指定关键词回复"""
        settings = self.get_settings()
        group_id = self._get_group_id(event)
        if not group_id and settings.get("group_separate", True):
            yield event.plain_result("❌ 此功能仅限群聊使用")
            return
        if not self._is_admin(event):
            yield event.plain_result("❌ 权限不足，需要管理员权限")
            return
            
        full_msg = event.get_message_str()
        keyword = full_msg.replace("/禁用回复", "").replace("禁用回复", "").strip()
        if not keyword:
            yield event.plain_result("❌ 请提供要禁用的关键字")
            return
            
        updated = False
        if group_id:
            group_cfg = self._get_group_config(group_id)
            if keyword in group_cfg:
                group_cfg[keyword]["enabled"] = False
                updated = True
                
        if not updated:
            global_cfg = self._get_global_config()
            if keyword in global_cfg:
                global_cfg[keyword]["enabled"] = False
                updated = True
                
        if not updated:
            yield event.plain_result(f"❌ 未找到关键词：{keyword}")
            return
            
        self._save_config()
        yield event.plain_result(f"✅ 已禁用关键词：{keyword}")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_message(self, event: AstrMessageEvent):
        settings = self.get_settings()
        reply_with_at = settings.get("reply_with_at", True)
        msg = event.message_str.strip()
        
        if not msg:
            return
            
        group_id = self._get_group_id(event)
        reply_data = None
        
        # 查找匹配的回复
        if group_id:
            group_cfg = self._get_group_config(group_id)
            if msg in group_cfg:
                reply_data = group_cfg[msg]
                
        if not reply_data:
            global_cfg = self._get_global_config()
            if msg in global_cfg:
                reply_data = global_cfg[msg]
                
        if not reply_data or not reply_data.get("enabled", True):
            return
            
        raw_content = reply_data.get("raw", "")
        chain = []
        
        # 群聊中@用户
        if reply_with_at and group_id:
            chain.append(Comp.At(qq=event.get_sender_id()))
            chain.append(Comp.Plain("\n"))  # 确保@后换行
        
        # 解析回复内容
        reply_chain = self._parse_reply_to_message_chain(raw_content)
        chain.extend(reply_chain)
        
        if chain:
            yield event.chain_result(chain)

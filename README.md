# AstrBot 智能回复插件

一个功能丰富的自定义关键词回复插件，支持文字、图片、正则表达式匹配。

![版本](https://img.shields.io/badge/版本-v2.0-blue)
![Python](https://img.shields.io/badge/Python-3.8+-green)
![AstrBot](https://img.shields.io/badge/AstrBot-插件-orange)

## ✨ 功能特性

- 📝 **文字回复** - 支持基础文字回复
- 🖼️ **图片回复** - 支持JPG/PNG格式图片回复
- 🔍 **正则匹配** - 支持正则表达式灵活匹配
- ⚡ **智能匹配** - 精确匹配和模糊匹配模式
- 🎯 **权限管理** - 管理员权限控制
- 🔄 **状态管理** - 启用/禁用规则控制
- 📋 **便捷管理** - 序号管理，操作简单

## 🚀 安装方法

### 自动安装（推荐）
1. 将 `plugin_reply.py` 下载到 AstrBot 的插件目录
2. 重启 AstrBot 服务
3. 插件会自动创建数据目录和配置文件

### 手动安装
```bash
# 克隆仓库
git clone https://github.com/MUxiaokalami/astrbot_plugin_reply.git

# 复制插件文件
cp astrbot_plugin_reply/plugin_reply.py /path/to/your/astrbot/plugins/

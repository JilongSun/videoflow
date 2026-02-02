"""
Theme detection and management utilities for TikHub Downloader
"""

import os
import platform
import logging
from tkinter import ttk

# 设置日志记录器
logger = logging.getLogger(__name__)

# ttkbootstrap主题映射
THEME_MAP = {
    'light': [
        'flatly',      # 平滑简约
        'cosmo',       # 简洁现代
        'lumen',       # 明亮简约
        'yeti',        # 清爽现代
        'pulse',       # 活力明亮
        'sandstone',   # 砂岩质感
        'litera',      # 书籍风格
        'minty',       # 薄荷清新
        'morph',       # 柔和形态
        'journal',     # 杂志样式
        'simplex',     # 简单明了
    ],
    'dark': [
        'superhero',   # 超级英雄
        'darkly',      # 深色极简
        'cyborg',      # 机械风格
        'vapor',       # 蒸汽朋克
        'solar',       # 太阳能风格
        'slate',       # 板岩风格
    ]
}

# 默认主题
DEFAULT_LIGHT_THEME = 'flatly'
DEFAULT_DARK_THEME = 'superhero'


def detect_system_theme():
    """
    检测当前操作系统的主题设置（深色或浅色）

    Returns:
        str: 'dark' 或 'light'
    """
    system = platform.system()

    try:
        if system == "Windows":
            try:
                # 尝试使用Windows Registry检测主题
                import winreg
                registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return 'light' if value == 1 else 'dark'
            except Exception as e:
                logger.debug(f"Failed to detect Windows theme: {e}")
                return 'light'

        elif system == "Darwin":  # macOS
            try:
                # 尝试使用macOS命令检测主题
                cmd = 'defaults read -g AppleInterfaceStyle'
                result = os.popen(cmd).read().strip()
                return 'dark' if result == 'Dark' else 'light'
            except Exception as e:
                logger.debug(f"Failed to detect macOS theme: {e}")
                return 'light'

        elif system == "Linux":
            try:
                # 尝试检测GNOME主题
                if os.environ.get('XDG_CURRENT_DESKTOP') in ['GNOME', 'Unity', 'Pantheon']:
                    cmd = 'gsettings get org.gnome.desktop.interface color-scheme'
                    result = os.popen(cmd).read().strip()
                    return 'dark' if 'dark' in result.lower() else 'light'

                # 尝试检测KDE主题
                elif os.environ.get('XDG_CURRENT_DESKTOP') == 'KDE':
                    cmd = 'kreadconfig5 --group "General" --key "ColorScheme" --file kdeglobals'
                    result = os.popen(cmd).read().strip()
                    return 'dark' if 'dark' in result.lower() else 'light'

                # 其他环境
                else:
                    return 'light'
            except Exception as e:
                logger.debug(f"Failed to detect Linux theme: {e}")
                return 'light'

        # 其他操作系统默认使用浅色主题
        return 'light'

    except Exception as e:
        logger.error(f"Error detecting system theme: {e}")
        return 'light'  # 默认浅色主题


def get_theme_name(theme_setting):
    """
    根据配置将主题设置转换为ttkbootstrap主题名

    Args:
        theme_setting (str): 配置中的主题设置 ('light', 'dark', 'system')

    Returns:
        str: ttkbootstrap主题名
    """
    try:
        # 处理'system'设置
        if theme_setting == 'system':
            system_theme = detect_system_theme()
            logger.info(f"Detected system theme: {system_theme}")
            theme_setting = system_theme

        # 获取对应色调的默认主题
        if theme_setting == 'dark':
            return DEFAULT_DARK_THEME
        else:  # 'light'或其他未知值都使用浅色主题
            return DEFAULT_LIGHT_THEME

    except Exception as e:
        logger.error(f"Error getting theme name: {e}")
        return DEFAULT_LIGHT_THEME  # 出错时使用默认浅色主题


def change_theme_at_runtime(root, theme_name):
    """
    在运行时更改应用主题

    Args:
        root: ttk.Window实例
        theme_name (str): ttkbootstrap主题名

    Returns:
        bool: 是否成功更改主题
    """
    try:
        style = ttk.Style()
        style.theme_use(theme_name)
        return True
    except Exception as e:
        logger.error(f"Error changing theme at runtime: {e}")
        return False
#!/usr/bin/env python3
"""
PTY 终端录制器

每隔指定时间读取 output.bin，使用虚拟终端渲染，
保存为 HTML 快照（最保真）。

依赖: pip install pyte
"""

import os
import sys
import time
import html
import json
import re
from datetime import datetime

# 尝试导入 pyte（终端模拟器库）
try:
    import pyte
except ImportError:
    print("请先安装 pyte: pip install pyte")
    sys.exit(1)

# ==================== 配置 ====================

# 录制间隔（秒）
RECORD_INTERVAL = 5

# 默认终端尺寸（如果无法读取实际尺寸时使用）
DEFAULT_COLS = 120
DEFAULT_ROWS = 30

# 输入输出路径
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
RAW_OUTPUT_FILE = os.path.join(LOG_DIR, "output.bin")
TERM_SIZE_FILE = os.path.join(LOG_DIR, "term_size.json")
SNAPSHOTS_DIR = os.path.join(LOG_DIR, "snapshots")

# ==================== ANSI 颜色映射 ====================

# 标准 16 色
COLORS_16 = {
    'black': '#000000',
    'red': '#cd0000',
    'green': '#00cd00',
    'brown': '#cdcd00',
    'blue': '#0000ee',
    'magenta': '#cd00cd',
    'cyan': '#00cdcd',
    'white': '#e5e5e5',
    # 亮色
    'light_black': '#7f7f7f',
    'light_red': '#ff0000',
    'light_green': '#00ff00',
    'light_brown': '#ffff00',
    'light_blue': '#5c5cff',
    'light_magenta': '#ff00ff',
    'light_cyan': '#00ffff',
    'light_white': '#ffffff',
}

# 默认颜色
DEFAULT_FG = '#c0c0c0'
DEFAULT_BG = '#0d1117'


def preprocess_ansi(text):
    """
    预处理 ANSI 序列，修复 pyte 的解析问题
    
    pyte bug: 
    - \x1b[>...m 是私有模式序列，但 pyte 错误地将其解析为 SGR
    - 例如 \x1b[>4;1m 会被误解析为"下划线开启"
    """
    # 移除私有模式序列 \x1b[>...m（这些不是 SGR，不应影响文本样式）
    # 格式: ESC [ > ... m
    text = re.sub(r'\x1b\[>[0-9;]*m', '', text)
    
    # 移除其他可能导致问题的私有序列
    # \x1b[?...m 也可能被误解析
    text = re.sub(r'\x1b\[\?[0-9;]*m', '', text)
    
    return text


def get_term_size():
    """
    从 term_size.json 读取实际终端尺寸
    如果文件不存在或读取失败，返回默认尺寸
    """
    try:
        if os.path.exists(TERM_SIZE_FILE):
            with open(TERM_SIZE_FILE, 'r') as f:
                data = json.load(f)
                cols = data.get('cols', DEFAULT_COLS)
                rows = data.get('rows', DEFAULT_ROWS)
                return cols, rows
    except Exception as e:
        print(f"警告: 无法读取终端尺寸: {e}")
    
    return DEFAULT_COLS, DEFAULT_ROWS


def color_to_css(color, default):
    """将 pyte 颜色转换为 CSS 颜色"""
    if color is None or color == 'default':
        return default
    if color in COLORS_16:
        return COLORS_16[color]
    if isinstance(color, str) and color.startswith('#'):
        return color
    # 256 色或 RGB
    if isinstance(color, tuple):
        return f'rgb({color[0]},{color[1]},{color[2]})'
    return default


def render_to_html(screen, cols, rows):
    """
    将 pyte Screen 渲染为 HTML
    
    Args:
        screen: pyte.Screen 对象
        cols: 终端列数
        rows: 终端行数
    
    Returns:
        完整的 HTML 字符串
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # HTML 头部
    html_parts = [f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PTY 终端快照 - {timestamp}</title>
    <style>
        body {{
            background: {DEFAULT_BG};
            margin: 0;
            padding: 20px;
            font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
        }}
        .terminal {{
            background: {DEFAULT_BG};
            color: {DEFAULT_FG};
            padding: 15px;
            border-radius: 8px;
            font-size: 14px;
            line-height: 1.4;
            white-space: pre;
            overflow-x: auto;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }}
        .header {{
            color: #888;
            margin-bottom: 10px;
            font-size: 12px;
        }}
        .cursor {{
            background: #58a6ff;
            color: {DEFAULT_BG};
        }}
        .bold {{ font-weight: bold; }}
        .italic {{ font-style: italic; }}
        .underline {{ text-decoration: underline; }}
        .blink {{ animation: blink 1s infinite; }}
        @keyframes blink {{
            50% {{ opacity: 0; }}
        }}
    </style>
</head>
<body>
    <div class="header">PTY 终端快照 | {timestamp} | {cols}x{rows}</div>
    <div class="terminal">''']
    
    # 渲染每一行
    for y in range(screen.lines):
        line_html = []
        
        for x in range(screen.columns):
            char = screen.buffer[y][x]
            
            # 获取字符和样式
            text = char.data if char.data else ' '
            text = html.escape(text)
            
            # 构建样式
            styles = []
            classes = []
            
            # 前景色
            fg = color_to_css(char.fg, DEFAULT_FG)
            if fg != DEFAULT_FG:
                styles.append(f'color:{fg}')
            
            # 背景色
            bg = color_to_css(char.bg, DEFAULT_BG)
            if bg != DEFAULT_BG:
                styles.append(f'background:{bg}')
            
            # 其他样式
            if char.bold:
                classes.append('bold')
            if char.italics:
                classes.append('italic')
            if char.underscore:
                classes.append('underline')
            if char.blink:
                classes.append('blink')
            
            # 光标位置
            if y == screen.cursor.y and x == screen.cursor.x:
                classes.append('cursor')
            
            # 生成 HTML
            if styles or classes:
                class_str = f' class="{" ".join(classes)}"' if classes else ''
                style_str = f' style="{";".join(styles)}"' if styles else ''
                line_html.append(f'<span{class_str}{style_str}>{text}</span>')
            else:
                line_html.append(text)
        
        html_parts.append(''.join(line_html))
        if y < screen.lines - 1:
            html_parts.append('\n')
    
    html_parts.append('''</div>
</body>
</html>''')
    
    return ''.join(html_parts)


def create_snapshot():
    """
    读取 output.bin，渲染并保存 HTML 快照
    
    Returns:
        (保存的文件路径, cols, rows)，失败返回 (None, 0, 0)
    """
    if not os.path.exists(RAW_OUTPUT_FILE):
        return None, 0, 0
    
    # 创建快照目录
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    
    # 获取实际终端尺寸
    cols, rows = get_term_size()
    
    # 创建虚拟终端（使用实际尺寸）
    # 使用 HistoryScreen 可以更好地处理滚动
    screen = pyte.Screen(cols, rows)
    screen.set_mode(pyte.modes.LNM)  # 自动换行模式
    stream = pyte.Stream(screen)
    
    # 启用对更多转义序列的支持
    stream.use_utf8 = True
    
    # 读取并解析 output.bin
    with open(RAW_OUTPUT_FILE, 'rb') as f:
        data = f.read()
    
    # 解码
    try:
        text = data.decode('utf-8', errors='replace')
    except Exception as e:
        print(f"解码错误: {e}")
        return None, 0, 0
    
    # 预处理：修复 pyte 的 ANSI 解析 bug
    text = preprocess_ansi(text)
    
    # 智能截取：查找最后一次备用屏幕切换或清屏
    # \x1b[?1049h = 切换到备用屏幕
    # \x1b[?1049l = 切换回主屏幕
    # \x1b[2J = 清屏
    # \x1b[H = 光标归位
    
    # 查找最后一次备用屏幕进入
    alt_screen_enter = text.rfind('\x1b[?1049h')
    alt_screen_exit = text.rfind('\x1b[?1049l')
    
    # 如果在备用屏幕中，从进入点开始解析
    if alt_screen_enter > alt_screen_exit:
        text = text[alt_screen_enter:]
    else:
        # 否则查找最后一次完整清屏
        last_clear = text.rfind('\x1b[2J')
        if last_clear > 0:
            # 保留清屏之后的内容，但也保留一些之前的内容以获取正确状态
            text = text[max(0, last_clear - 1000):]
    
    # 输入到虚拟终端
    try:
        stream.feed(text)
    except Exception as e:
        print(f"解析错误: {e}")
        return None, 0, 0
    
    # 渲染为 HTML（传入实际尺寸）
    html_content = render_to_html(screen, cols, rows)
    
    # 保存文件
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"snapshot_{timestamp}.html"
    filepath = os.path.join(SNAPSHOTS_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # 同时保存一个 latest.html 软链接/副本
    latest_path = os.path.join(SNAPSHOTS_DIR, "latest.html")
    with open(latest_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return filepath, cols, rows


def main():
    """主循环：每隔 RECORD_INTERVAL 秒保存一次快照"""
    print(f"PTY 终端录制器")
    print(f"=" * 50)
    print(f"录制间隔: {RECORD_INTERVAL} 秒")
    print(f"尺寸来源: {TERM_SIZE_FILE}")
    print(f"输入文件: {RAW_OUTPUT_FILE}")
    print(f"快照目录: {SNAPSHOTS_DIR}")
    print(f"=" * 50)
    print(f"按 Ctrl+C 停止录制")
    print()
    
    snapshot_count = 0
    last_size = (0, 0)
    
    try:
        while True:
            filepath, cols, rows = create_snapshot()
            if filepath:
                snapshot_count += 1
                size_info = f"{cols}x{rows}"
                if (cols, rows) != last_size:
                    size_info += " (尺寸更新)"
                    last_size = (cols, rows)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 快照 #{snapshot_count}: {os.path.basename(filepath)} [{size_info}]")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 等待输出...")
            
            time.sleep(RECORD_INTERVAL)
            
    except KeyboardInterrupt:
        print(f"\n录制结束，共保存 {snapshot_count} 个快照")
        print(f"查看最新快照: open {SNAPSHOTS_DIR}/latest.html")


if __name__ == '__main__':
    main()


#!/usr/bin/env python3
"""
PTY 虚拟终端专属命令

这些命令只在 PTY 虚拟终端中可用。
使用方法: python3 pty_commands.py <command> [args]
"""

import os
import sys
import subprocess
import shutil

# ==================== 颜色定义 ====================

class Colors:
    CYAN = '\033[1;36m'
    YELLOW = '\033[1;33m'
    GREEN = '\033[1;32m'
    RED = '\033[1;31m'
    GRAY = '\033[90m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


# ==================== 命令实现 ====================

def cmd_info():
    """显示 PTY 终端信息"""
    # 获取终端尺寸
    size = shutil.get_terminal_size((80, 24))
    
    print(f"{Colors.CYAN}╔══════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.CYAN}║     PTY 虚拟终端信息                 ║{Colors.RESET}")
    print(f"{Colors.CYAN}╠══════════════════════════════════════╣{Colors.RESET}")
    print(f"{Colors.CYAN}║{Colors.RESET}  PTY_TERMINAL: {os.environ.get('PTY_TERMINAL', 'N/A')}")
    print(f"{Colors.CYAN}║{Colors.RESET}  SHELL: {os.environ.get('SHELL', 'N/A')}")
    print(f"{Colors.CYAN}║{Colors.RESET}  TERM: {os.environ.get('TERM', 'N/A')}")
    print(f"{Colors.CYAN}║{Colors.RESET}  终端尺寸: {size.columns}x{size.lines}")
    print(f"{Colors.CYAN}║{Colors.RESET}  PID: {os.getpid()}")
    print(f"{Colors.CYAN}║{Colors.RESET}  Python: {sys.version.split()[0]}")
    print(f"{Colors.CYAN}╚══════════════════════════════════════╝{Colors.RESET}")


def cmd_help():
    """显示帮助信息"""
    print(f"{Colors.YELLOW}🔧 PTY 虚拟终端专属命令:{Colors.RESET}")
    print()
    print(f"  {Colors.GREEN}pty_info{Colors.RESET}    - 显示 PTY 终端信息")
    print(f"  {Colors.GREEN}pty_help{Colors.RESET}    - 显示此帮助信息")
    print(f"  {Colors.GREEN}pty_log{Colors.RESET}     - 查看最近的日志")
    print(f"  {Colors.GREEN}pty_rawlog{Colors.RESET}  - 查看原始输出文件")
    print(f"  {Colors.GREEN}pty_clear{Colors.RESET}   - 清屏并显示欢迎信息")
    print(f"  {Colors.GREEN}pty_colors{Colors.RESET}  - 测试终端颜色支持")
    print()
    print(f"{Colors.GRAY}提示: 这些命令只在 PTY 虚拟终端中可用{Colors.RESET}")


def cmd_log():
    """查看最近日志"""
    log_file = os.environ.get('PTY_LOG_FILE', '')
    if not log_file or not os.path.exists(log_file):
        print(f"{Colors.RED}错误: 日志文件不存在{Colors.RESET}")
        return
    
    print(f"{Colors.YELLOW}📋 最近日志 (最后 20 行):{Colors.RESET}")
    print()
    with open(log_file, 'r') as f:
        lines = f.readlines()
        for line in lines[-20:]:
            print(line, end='')


def cmd_rawlog():
    """查看原始输出"""
    raw_file = os.environ.get('PTY_RAW_OUTPUT_FILE', '')
    if not raw_file or not os.path.exists(raw_file):
        print(f"{Colors.RED}错误: 原始输出文件不存在{Colors.RESET}")
        return
    
    print(f"{Colors.YELLOW}📦 原始输出文件 (最后 200 字节):{Colors.RESET}")
    print()
    
    # 读取最后 200 字节并以十六进制显示
    with open(raw_file, 'rb') as f:
        f.seek(0, 2)  # 移到文件末尾
        size = f.tell()
        start = max(0, size - 200)
        f.seek(start)
        data = f.read()
    
    # 简单的 hexdump
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'{i:08x}  {hex_part:<48}  |{ascii_part}|')


def cmd_clear():
    """清屏并显示欢迎信息"""
    os.system('clear')
    print(f"{Colors.CYAN}╔══════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.CYAN}║   🖥️  PTY 虚拟终端                   ║{Colors.RESET}")
    print(f"{Colors.CYAN}║   输入 pty_help 查看专属命令         ║{Colors.RESET}")
    print(f"{Colors.CYAN}╚══════════════════════════════════════╝{Colors.RESET}")
    print()


def cmd_colors():
    """测试终端颜色"""
    print(f"{Colors.YELLOW}🎨 终端颜色测试:{Colors.RESET}")
    print()
    
    # 基本颜色
    colors = [30, 31, 32, 33, 34, 35, 36, 37]
    
    # 亮色
    print(' '.join(f'\033[1;{c}m██\033[0m' for c in colors) + '  亮色')
    # 暗色
    print(' '.join(f'\033[0;{c}m██\033[0m' for c in colors) + '  暗色')
    print()
    
    # 样式
    print('\033[1m粗体\033[0m  \033[4m下划线\033[0m  \033[7m反色\033[0m  \033[5m闪烁\033[0m')
    print()
    
    # 256 色示例
    print('256 色示例:')
    for i in range(0, 256, 16):
        row = ''.join(f'\033[48;5;{j}m  \033[0m' for j in range(i, min(i+16, 256)))
        print(row)


# ==================== 主入口 ====================

COMMANDS = {
    'info': cmd_info,
    'help': cmd_help,
    'log': cmd_log,
    'rawlog': cmd_rawlog,
    'clear': cmd_clear,
    'colors': cmd_colors,
}


def main():
    if len(sys.argv) < 2:
        cmd_help()
        return
    
    cmd = sys.argv[1]
    
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(f"{Colors.RED}未知命令: {cmd}{Colors.RESET}")
        print(f"使用 'pty_help' 查看可用命令")
        sys.exit(1)


if __name__ == '__main__':
    main()



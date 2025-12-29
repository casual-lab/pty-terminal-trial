#!/usr/bin/env python3
"""
PTY 虚拟终端 - 命令行版

这是一个学习项目，演示 PTY（伪终端）的核心原理。
运行后会启动一个 shell，你可以像使用普通终端一样操作。

核心概念：
- PTY (Pseudo Terminal) 由 Master 和 Slave 两端组成
- Master 端：我们的程序控制，负责读写数据
- Slave 端：Shell 进程连接，认为自己在真实终端中
"""

import os
import pty
import sys
import tty
import termios
import select
import signal
import time
import logging
import json
from datetime import datetime

# ==================== 配置 ====================

# 日志目录
LOG_DIR = os.path.expanduser("log")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

# 日志文件路径
LOG_FILE = os.path.join(LOG_DIR, "pty_terminal.log")

# 原始输出二进制文件（保存所有 shell 输出的 raw 序列，包括 ANSI 转义码）
RAW_OUTPUT_FILE = os.path.join(LOG_DIR, "output.bin")

# 终端尺寸信息文件（供 recorder 读取）
TERM_SIZE_FILE = os.path.join(LOG_DIR, "term_size.json")

# 是否记录输入/输出的详细数据到日志
LOG_DATA = True

# 全局：原始输出文件句柄
raw_output_fd = None

# 自定义 prompt 配置
PTY_PROMPT_BASH = r'\[\033[1;36m\][PTY]\[\033[0m\] \[\033[33m\]\w\[\033[0m\] $ '
PTY_PROMPT_ZSH = '%F{cyan}%B[PTY]%b%f %F{yellow}%~%f $ '

# PTY 专属命令脚本（Python）
PTY_COMMANDS_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pty_commands.py")


def get_pty_shell_init():
    """
    生成 shell 初始化命令
    创建调用 Python 脚本的别名/函数
    """
    script_path = os.path.abspath(PTY_COMMANDS_SCRIPT)
    log_file = os.path.abspath(LOG_FILE)
    raw_output_file = os.path.abspath(RAW_OUTPUT_FILE)
    
    # 设置环境变量和创建命令别名
    init_commands = f'''
# PTY 虚拟终端环境
export PTY_TERMINAL=1
export PTY_LOG_FILE="{log_file}"
export PTY_RAW_OUTPUT_FILE="{raw_output_file}"
export PTY_COMMANDS_SCRIPT="{script_path}"

# PTY 专属命令（调用 Python 脚本）
pty_info()   {{ python3 "$PTY_COMMANDS_SCRIPT" info; }}
pty_help()   {{ python3 "$PTY_COMMANDS_SCRIPT" help; }}
pty_log()    {{ python3 "$PTY_COMMANDS_SCRIPT" log; }}
pty_rawlog() {{ python3 "$PTY_COMMANDS_SCRIPT" rawlog; }}
pty_clear()  {{ python3 "$PTY_COMMANDS_SCRIPT" clear; }}
pty_colors() {{ python3 "$PTY_COMMANDS_SCRIPT" colors; }}
'''
    return init_commands

# ==================== 日志配置 ====================

def setup_logging():
    """配置日志系统"""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger('pty_terminal')

logger = setup_logging()


def save_term_size(cols, rows):
    """
    保存终端尺寸到文件，供 recorder 读取
    """
    try:
        with open(TERM_SIZE_FILE, 'w') as f:
            json.dump({
                'cols': cols,
                'rows': rows,
                'updated': datetime.now().isoformat()
            }, f)
        logger.debug(f"已保存终端尺寸: {cols}x{rows}")
    except Exception as e:
        logger.warning(f"保存终端尺寸失败: {e}")


def create_pty_shell():
    """
    创建一个 PTY 并在其中运行 shell
    
    工作原理：
    1. pty.fork() 创建一个伪终端对 (master/slave)
    2. 在子进程中，stdin/stdout/stderr 连接到 slave 端
    3. 在父进程中，我们通过 master 端与子进程通信
    
    返回: (pid, master_fd)
        - pid: 子进程 ID (如果是父进程) 或 0 (如果是子进程)
        - master_fd: PTY master 端的文件描述符
    """
    logger.info("正在创建 PTY...")
    
    # fork 并创建 PTY
    pid, master_fd = pty.fork()
    
    if pid == 0:
        # ===== 子进程 =====
        # 此时 stdin/stdout/stderr 已自动连接到 PTY slave 端
        
        # 获取用户默认 shell
        shell = os.environ.get('SHELL', '/bin/bash')
        
        # 用 shell 替换当前进程
        os.execv(shell, [shell])
        
        # 如果 execv 失败
        sys.exit(1)
    
    # ===== 父进程 =====
    shell = os.environ.get('SHELL', '/bin/bash')
    logger.info(f"PTY 创建成功: PID={pid}, master_fd={master_fd}, shell={shell}")
    return pid, master_fd


def copy_data(master_fd, child_pid):
    """
    在终端和 PTY 之间双向复制数据
    
    数据流：
    - 用户键盘 → stdin(0) → master_fd → shell
    - shell 输出 → master_fd → stdout(1) → 屏幕
                            ↘ raw_output_fd → output.bin
    
    Args:
        master_fd: PTY master 端文件描述符
        child_pid: 子进程 PID
    """
    global raw_output_fd
    
    logger.info("开始数据复制循环")
    input_count = 0
    output_count = 0
    
    try:
        while True:
            ready, _, _ = select.select([sys.stdin, master_fd], [], [])
            
            for fd in ready:
                if fd == sys.stdin:
                    # 用户输入 → 发送到 shell
                    data = os.read(sys.stdin.fileno(), 1024)
                    if data:
                        os.write(master_fd, data)
                        input_count += len(data)
                        if LOG_DATA:
                            logger.debug(f"INPUT ({len(data)} bytes): {repr(data)}")
                    else:
                        logger.info("stdin 关闭")
                        return
                        
                elif fd == master_fd:
                    # shell 输出 → 显示到屏幕
                    try:
                        data = os.read(master_fd, 1024)
                        if data:
                            # 写入屏幕
                            os.write(sys.stdout.fileno(), data)
                            # 写入原始输出文件
                            if raw_output_fd:
                                raw_output_fd.write(data)
                                raw_output_fd.flush()
                            output_count += len(data)
                            if LOG_DATA:
                                logger.debug(f"OUTPUT ({len(data)} bytes): {repr(data)}")
                        else:
                            logger.info("Shell 已退出")
                            return
                    except OSError as e:
                        logger.info(f"PTY 已关闭: {e}")
                        return
                        
    except (IOError, OSError) as e:
        logger.error(f"数据复制错误: {e}")
    finally:
        logger.info(f"数据复制结束: 输入 {input_count} 字节, 输出 {output_count} 字节")


def run_terminal():
    """
    主函数：运行虚拟终端
    
    步骤：
    1. 保存当前终端设置
    2. 将终端设置为 raw 模式（直接传递按键，不做处理）
    3. 创建 PTY 并运行 shell
    4. 在终端和 PTY 之间复制数据
    5. 恢复终端设置
    """
    global raw_output_fd
    
    logger.info("=" * 50)
    logger.info("PTY 虚拟终端启动")
    logger.info(f"日志文件: {LOG_FILE}")
    logger.info(f"原始输出文件: {RAW_OUTPUT_FILE}")
    logger.info("=" * 50)
    
    # 打开原始输出文件（二进制追加模式）
    raw_output_fd = open(RAW_OUTPUT_FILE, 'ab')
    # 写入会话分隔符
    session_header = f"\n{'='*50}\nSession: {datetime.now().isoformat()}\n{'='*50}\n".encode()
    raw_output_fd.write(session_header)
    logger.info("已打开原始输出文件")
    
    # 保存当前终端属性，以便退出时恢复
    old_tty_attrs = termios.tcgetattr(sys.stdin)
    logger.debug("已保存终端属性")
    
    try:
        # 将终端设置为 raw 模式
        tty.setraw(sys.stdin.fileno())
        logger.debug("终端已设置为 raw 模式")
        
        # 创建 PTY 并启动 shell
        child_pid, master_fd = create_pty_shell()
        
        # 设置窗口大小（让 shell 知道终端尺寸）
        try:
            import fcntl
            import struct
            size = fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, b'\x00' * 8)
            rows, cols = struct.unpack('HH', size[:4])
            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, size)
            save_term_size(cols, rows)  # 保存尺寸供 recorder 使用
            logger.info(f"终端尺寸: {cols}x{rows}")
        except Exception as e:
            logger.warning(f"无法设置终端尺寸: {e}")
        
        # 处理窗口大小变化信号
        def handle_resize(signum, frame):
            try:
                size = fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, b'\x00' * 8)
                rows, cols = struct.unpack('HH', size[:4])
                fcntl.ioctl(master_fd, termios.TIOCSWINSZ, size)
                save_term_size(cols, rows)  # 更新尺寸供 recorder 使用
                logger.info(f"窗口大小变化: {cols}x{rows}")
            except Exception as e:
                logger.warning(f"处理窗口大小变化失败: {e}")
        
        signal.signal(signal.SIGWINCH, handle_resize)
        logger.debug("已注册 SIGWINCH 信号处理器")
        
        # 等待 shell 初始化完成，然后注入自定义命令和 prompt
        time.sleep(0.1)
        
        # 注入 PTY 专属命令（shell 函数调用 Python 脚本）
        shell_init = get_pty_shell_init()
        os.write(master_fd, shell_init.encode())
        os.write(master_fd, b"\n")
        logger.info(f"已注入 PTY 专属命令 (Python: {PTY_COMMANDS_SCRIPT})")
        
        # 设置自定义 prompt
        shell = os.environ.get('SHELL', '/bin/bash')
        if 'zsh' in shell:
            prompt_cmd = f"PROMPT='{PTY_PROMPT_ZSH}'\n"
        else:
            prompt_cmd = f"PS1='{PTY_PROMPT_BASH}'\n"
        
        os.write(master_fd, prompt_cmd.encode())
        # 清屏并显示欢迎信息
        os.write(master_fd, b"pty_clear\n")
        logger.info("已设置自定义 prompt")
        
        # 开始数据复制循环
        copy_data(master_fd, child_pid)
        
        # 等待子进程结束
        _, status = os.waitpid(child_pid, 0)
        exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else -1
        logger.info(f"子进程退出: exit_code={exit_code}")
        
    finally:
        # 关闭原始输出文件
        if raw_output_fd:
            raw_output_fd.write(b"\n--- Session End ---\n")
            raw_output_fd.close()
            logger.info("已关闭原始输出文件")
        
        # 恢复终端设置
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty_attrs)
        logger.debug("已恢复终端属性")
        logger.info("PTY 虚拟终端关闭")
        logger.info("=" * 50)


def main():
    """入口函数"""
    print("=" * 50)
    print("PTY 虚拟终端 (学习版)")
    print("=" * 50)
    print("这是一个运行在 PTY 中的 shell")
    print("输入 'exit' 或按 Ctrl+D 退出")
    print(f"日志文件: {LOG_FILE}")
    print(f"原始输出: {RAW_OUTPUT_FILE}")
    print("=" * 50)
    print()
    
    run_terminal()
    
    print()
    print("终端会话已结束")
    print(f"查看日志: cat {LOG_FILE}")
    print(f"查看原始输出: hexdump -C {RAW_OUTPUT_FILE} | less")


if __name__ == "__main__":
    main()


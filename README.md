# PTY 虚拟终端 - 命令行版

一个最简化的 PTY（伪终端）实现，用于学习终端工作原理。

## 快速开始

```bash
python3 pty_terminal.py
```

输入 `exit` 或按 `Ctrl+D` 退出。

运行后你会看到一个带有 **[PTY]** 标识的彩色 prompt：

```
[PTY] ~/Developer/pty-terminal $ 
```

### PTY 专属命令

PTY 虚拟终端内置了一些**只在 PTY 中可用**的命令：

| 命令 | 功能 |
|------|------|
| `pty_help` | 显示专属命令帮助 |
| `pty_info` | 显示 PTY 终端信息 |
| `pty_log` | 查看最近的日志 |
| `pty_rawlog` | 查看原始输出文件 |
| `pty_clear` | 清屏并显示欢迎信息 |
| `pty_colors` | 测试终端颜色支持 |

这些命令用 Python 实现，定义在 `pty_commands.py` 文件中。你可以自由添加自定义命令：

```python
# 在 pty_commands.py 中添加新命令
def cmd_demo():
    """我的自定义命令"""
    print("这是我的自定义命令")

# 在 COMMANDS 字典中注册
COMMANDS = {
    # ...
    'demo': cmd_demo,
}
```

### 查看日志

日志保存在 `log/` 目录：

```bash
# 查看文本日志
cat log/pty_terminal.log

# 查看原始输出（二进制，包含 ANSI 转义序列）
hexdump -C log/output.bin | less

# 或者直接 cat（会渲染 ANSI 颜色）
cat log/output.bin
```

#### 日志文件说明

| 文件 | 格式 | 内容 |
|------|------|------|
| `pty_terminal.log` | 文本 | 事件日志、时间戳、输入输出摘要 |
| `output.bin` | 二进制 | Shell 的完整原始输出，包含所有 ANSI 转义序列 |

#### 日志示例 (pty_terminal.log)

```
2025-01-01 12:00:00 [INFO] ==================================================
2025-01-01 12:00:00 [INFO] PTY 虚拟终端启动
2025-01-01 12:00:00 [INFO] 原始输出文件: log/output.bin
2025-01-01 12:00:00 [INFO] PTY 创建成功: PID=12345, master_fd=3, shell=/bin/zsh
2025-01-01 12:00:00 [INFO] 终端尺寸: 120x30
2025-01-01 12:00:00 [DEBUG] INPUT (3 bytes): b'ls\n'
2025-01-01 12:00:00 [DEBUG] OUTPUT (156 bytes): b'\x1b[1m...'
2025-01-01 12:00:01 [INFO] 数据复制结束: 输入 42 字节, 输出 1024 字节
2025-01-01 12:00:01 [INFO] 子进程退出: exit_code=0
```

#### 原始输出用途

`output.bin` 可用于：
- 分析 ANSI 转义序列（颜色、光标移动等）
- 回放终端会话
- 调试终端渲染问题

### 终端录制器

每隔 5 秒将 `output.bin` 重放渲染，保存为 **HTML 快照**（最保真）：

```bash
# 安装依赖
pip install pyte

# 启动录制器（在另一个终端窗口）
python3 pty_recorder.py
```

录制器会：
1. 读取 `output.bin` 中的原始序列
2. 使用 `pyte` 虚拟终端解析 ANSI 序列
3. 渲染为带样式的 HTML
4. 保存到 `log/snapshots/` 目录

```bash
# 查看最新快照
open log/snapshots/latest.html
```

HTML 快照保留：
- ✅ 所有颜色（16色、256色、RGB）
- ✅ 粗体、斜体、下划线、闪烁
- ✅ 光标位置
- ✅ 精确的字符布局

## 项目结构

```
pty-terminal/
├── pty_terminal.py   # 主程序
├── pty_commands.py   # PTY 专属命令（Python 实现）
├── pty_recorder.py   # 终端录制器（生成 HTML 快照）
├── log/
│   ├── pty_terminal.log   # 文本日志
│   ├── output.bin         # 原始输出
│   └── snapshots/         # HTML 快照目录
│       ├── latest.html    # 最新快照
│       └── snapshot_*.html
└── README.md         # 本文档
```

## 配置选项

在 `pty_terminal.py` 开头可以修改以下配置：

```python
# 日志目录
LOG_DIR = os.path.expanduser("log")

# 日志文件路径
LOG_FILE = os.path.join(LOG_DIR, "pty_terminal.log")

# 原始输出二进制文件
RAW_OUTPUT_FILE = os.path.join(LOG_DIR, "output.bin")

# 是否记录输入/输出的详细数据到日志（可能包含敏感信息）
LOG_DATA = True
```

## 核心原理

### 什么是 PTY？

PTY（Pseudo Terminal）是操作系统提供的一种机制，用于模拟硬件终端。

```
┌─────────────────────────────────────────────────────────────┐
│                       PTY 结构图                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────┐                     ┌─────────────┐       │
│   │  我们的程序  │ ←── Master 端 ───→ │  Shell      │       │
│   │  (父进程)   │                     │  (子进程)   │       │
│   └─────────────┘                     └─────────────┘       │
│         │                                   │               │
│         │ read/write                        │ stdin/stdout  │
│         ▼                                   ▼               │
│   ┌─────────────┐                     ┌─────────────┐       │
│   │  PTY Master │ ←───── PTY ──────→ │  PTY Slave  │       │
│   │  (文件描述符)│       双向通道      │  (虚拟终端)  │       │
│   └─────────────┘                     └─────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 代码架构

程序由 4 个函数组成：

| 函数 | 职责 |
|------|------|
| `main()` | 入口，显示欢迎信息 |
| `run_terminal()` | 主逻辑：设置 raw 模式、创建 PTY、处理信号 |
| `create_pty_shell()` | 创建 PTY 并 fork 子进程运行 shell |
| `copy_data()` | 在 stdin/stdout 和 PTY 之间双向复制数据 |

### 核心代码解析

#### 1. 创建 PTY 并 fork 子进程

```python
def create_pty_shell():
    # fork 并创建 PTY
    pid, master_fd = pty.fork()
    
    if pid == 0:
        # ===== 子进程 =====
        # 此时 stdin/stdout/stderr 已自动连接到 PTY slave 端
        shell = os.environ.get('SHELL', '/bin/bash')
        
        # 设置自定义 prompt，让 PTY 终端与正常终端有所区别
        os.environ['PS1'] = r'\033[1;36m[PTY]\033[0m \033[33m\w\033[0m $ '  # bash
        os.environ['PROMPT'] = '%F{cyan}%B[PTY]%b%f %F{yellow}%~%f $ '     # zsh
        
        os.execv(shell, [shell])  # 用 shell 替换当前进程
        sys.exit(1)
    
    # ===== 父进程 =====
    return pid, master_fd
```

#### 2. 设置 Raw 模式

```python
def run_terminal():
    # 保存当前终端属性，以便退出时恢复
    old_tty_attrs = termios.tcgetattr(sys.stdin)
    
    try:
        # 将终端设置为 raw 模式
        # raw 模式下：
        # - 按键直接传递，不等待回车
        # - 不回显字符
        # - Ctrl+C 等不产生信号，直接传递
        tty.setraw(sys.stdin.fileno())
        
        # ... 创建 PTY、复制数据 ...
        
    finally:
        # 恢复终端设置
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty_attrs)
```

#### 3. 双向数据复制

```python
def copy_data(master_fd, child_pid):
    while True:
        # 使用 select 同时监听两个输入源
        ready, _, _ = select.select([sys.stdin, master_fd], [], [])
        
        for fd in ready:
            if fd == sys.stdin:
                # 用户输入 → 发送到 shell
                data = os.read(sys.stdin.fileno(), 1024)
                if data:
                    os.write(master_fd, data)
                    
            elif fd == master_fd:
                # shell 输出 → 显示到屏幕
                data = os.read(master_fd, 1024)
                if data:
                    os.write(sys.stdout.fileno(), data)
```

#### 4. 处理窗口大小变化

```python
# 设置窗口大小（让 vim、top 等程序正确显示）
size = fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, b'\x00' * 8)
fcntl.ioctl(master_fd, termios.TIOCSWINSZ, size)

# 处理 SIGWINCH 信号（窗口大小变化时触发）
def handle_resize(signum, frame):
    size = fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, b'\x00' * 8)
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, size)

signal.signal(signal.SIGWINCH, handle_resize)
```

### 数据流图

```
┌──────────────────────────────────────────────────────────────────┐
│                         数据流                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   键盘输入                                                        │
│      │                                                           │
│      ▼                                                           │
│   ┌──────┐   read    ┌──────────┐   write   ┌──────────┐        │
│   │ stdin │ ───────→ │  父进程   │ ───────→ │ master_fd│        │
│   └──────┘           └──────────┘           └──────────┘        │
│                                                   │              │
│                                               PTY 内核           │
│                                                   │              │
│   ┌──────┐   write   ┌──────────┐   read    ┌──────────┐        │
│   │stdout │ ←─────── │  父进程   │ ←─────── │ master_fd│        │
│   └──────┘           └──────────┘           └──────────┘        │
│      │                                                           │
│      ▼                                                           │
│   屏幕显示                                                        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 关键系统调用

| 函数 | 作用 |
|------|------|
| `pty.fork()` | 创建 PTY 对并 fork 进程 |
| `os.execv()` | 用新程序替换当前进程 |
| `tty.setraw()` | 设置终端为 raw 模式 |
| `termios.tcgetattr/tcsetattr()` | 获取/设置终端属性 |
| `select.select()` | 同时监听多个文件描述符 |
| `os.read/write()` | 读写文件描述符 |
| `fcntl.ioctl()` | 设备控制（如获取/设置窗口大小） |
| `signal.signal()` | 注册信号处理函数 |
| `os.waitpid()` | 等待子进程结束 |

### Raw 模式 vs 正常模式

| 特性 | 正常模式 | Raw 模式 |
|------|----------|----------|
| 按键传递 | 缓冲到回车 | 立即传递 |
| 字符回显 | 系统处理 | 不回显 |
| Ctrl+C | 产生 SIGINT | 直接传递字符 |
| 退格键 | 系统处理 | 直接传递 |

我们需要 raw 模式，因为 shell 自己会处理回显和行编辑。

## 与 Termux 的对比

| 组件 | 本项目 | Termux |
|------|--------|--------|
| 语言 | Python | Java + C |
| PTY 创建 | `pty.fork()` | `forkpty()` (JNI) |
| 终端渲染 | 系统终端 | 自定义 TerminalView |
| 输入处理 | `select()` | Android 事件系统 |

核心原理完全一致！

## 依赖

无外部依赖，仅使用 Python 标准库：
- `os`, `sys` - 系统接口
- `pty` - 伪终端
- `tty`, `termios` - 终端控制
- `select` - I/O 多路复用
- `signal` - 信号处理
- `fcntl` - 文件控制

## 扩展阅读

- `man 7 pty` - PTY 手册
- `man 3 forkpty` - forkpty 函数
- `man 4 tty` - TTY 设备
- [Termux 终端模拟器源码](https://github.com/termux/termux-app)

## License

MIT

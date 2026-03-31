# ClearMem - 定时清除目录程序

一个 Windows 桌面应用程序，支持定时清除指定目录和 RDP 远程桌面登录后自动清除目录。

## 功能特性

- **定时清除**: 支持间隔模式和指定时间点两种模式
- **RDP 自动清除**: 检测 Windows 远程桌面(RDP)登录事件，登录后自动清除目录
- **系统托盘**: 最小化到右下角任务栏，后台运行
- **配置持久化**: 设置自动保存，重启后保持

## 默认配置

- 默认清除目录: `D:\cache\.ws`
- 默认启用 RDP 自动清除
- 定时清除默认关闭

---

## Python 版本

### 安装依赖

```bash
pip install pystray Pillow pywin32
```

### 运行程序

```bash
python main.py
```

### 打包为 EXE

```bash
python build_exe.py
```

打包完成后，可执行文件位于 `dist/ClearMem.exe`

---

## C# 版本

### 环境要求

- .NET 8.0 SDK

### 运行程序

```bash
cd ClearMem
dotnet run
```

### 打包发布

```bash
cd ClearMem
dotnet publish -c Release -o ./publish
```

---

## 使用说明

### 主界面

- **基础设置**: 设置目标目录、启用/禁用 RDP 自动清除
- **定时设置**: 启用定时清除，选择间隔模式或指定时间点
- **关于**: 程序信息

### 系统托盘

- 关闭窗口时，程序最小化到右下角托盘
- 托盘图标右键菜单:
  - 显示: 打开主窗口
  - 清除缓存: 立即执行清除
  - 退出: 完全退出程序

### 配置说明

- 配置文件: `config.json` (自动生成)
- 日志文件: `clearMem.log`

## 许可证

MIT License
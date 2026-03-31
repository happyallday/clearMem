# Nuitka打包脚本 for ClearMem
# 安装 Nuitka: pip install nuitka
# 运行: python build_exe.py

import os
import subprocess
import sys

def build():
    cmd = [
        sys.executable, '-m', 'nuitka',
        '--standalone',
        '--onefile',
        '--windows-disable-console',
        '--windows-icon-from-ico=NONE',
        '--include-data-dir=pystray=pystray',
        '--plugin-enable=tinter',
        '--plugin-enable=pylint',
        '--follow-imports',
        '--include-module=pystray',
        '--include-module=PIL',
        '--output-dir=dist',
        'main.py'
    ]
    
    print('开始打包...')
    print('命令:', ' '.join(cmd))
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print('打包成功! 输出目录: dist')
    else:
        print('打包失败!')
        sys.exit(1)

if __name__ == '__main__':
    build()
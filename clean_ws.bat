@echo off
echo 正在清理 D:\cache\.ws 目录...
del /f /s /q "D:\cache\.ws\*.*" 2>nul
echo 清理完成！
pause
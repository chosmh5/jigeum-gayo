@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "c:\Users\kkk42\Desktop\aiai\data-collector"
if not exist logs mkdir logs
"C:\Users\kkk42\AppData\Local\Programs\Python\Python311\python.exe" scheduler.py >> "logs\scheduler.log" 2>&1

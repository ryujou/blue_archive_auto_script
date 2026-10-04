@echo off
cd /d "%~dp0"
".env\python.exe" -c "import sys,site,runpy; sys.path.insert(0,'.'); site.addsitedir('.venv/Lib/site-packages'); runpy.run_path('window.py',run_name='__main__')"

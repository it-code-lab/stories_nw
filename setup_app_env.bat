@echo off
py -3.11 -m venv venv
call venv\Scripts\activate
python -m pip install -U pip setuptools wheel
pip install -r requirements-app.txt
echo Environment ready.
pause

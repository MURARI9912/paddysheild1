@echo off
echo.
echo  ====================================
echo   PaddyShield - Starting App...
echo  ====================================
echo.
echo  Installing requirements...
pip install -r requirements.txt --quiet
echo.
echo  Starting server...
echo  Open your browser at: http://localhost:5000
echo.
python app.py
pause

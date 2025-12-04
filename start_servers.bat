@echo off
echo Starting RAG Chatbot servers...
echo.

echo Creating .env file from template...
copy backend\.env.example backend\.env

echo Starting Backend Server (Flask)...
start "Backend Server" cmd /k "cd backend && python app.py"

echo Waiting 5 seconds for backend to start...
timeout /t 5 /nobreak > nul

echo Starting Frontend Server (React)...
start "Frontend Server" cmd /k "cd frontend && npm start"

echo.
echo Both servers are starting...
echo Backend: http://localhost:5000
echo Frontend: http://localhost:3000
echo.
pause

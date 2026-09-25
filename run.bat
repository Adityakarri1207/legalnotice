@echo off
echo ========================================================
echo   JurisClear AI — GenAI Legal Intelligence Platform
echo   Powered by Google Gemini 3.8 Flash & Built-in Engine
echo ========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Initializing with uv...
    "%USERPROFILE%\.local\bin\uv.exe" venv .venv
    "%USERPROFILE%\.local\bin\uv.exe" pip install fastapi uvicorn pydantic python-multipart pypdf python-docx httpx google-genai
)

echo [INFO] Starting JurisClear AI Server on http://localhost:8000 ...
echo [INFO] Open your browser and navigate to http://localhost:8000
echo.

start http://localhost:8000
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause

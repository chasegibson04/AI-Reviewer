@echo off
cd /d "%~dp0"
echo --- Starting Claude Review Interactive Session ---
npx tsx src/index.ts
if %errorlevel% neq 0 pause

@echo off
rem Gera dist\BancoDeDados.exe a partir do codigo. Precisa do Python instalado
rem so em quem GERA; quem USA o .exe nao precisa de nada.
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller matplotlib numpy pillow openpyxl || goto erro
python -m PyInstaller --noconfirm --clean banco_de_dados.spec || goto erro
echo.
echo Pronto: dist\BancoDeDados.exe
pause
exit /b 0
:erro
echo.
echo Deu erro ao gerar o executavel (veja as mensagens acima).
pause
exit /b 1

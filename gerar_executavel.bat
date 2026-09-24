@echo off
rem Gera os executaveis em dist\ a partir do codigo:
rem   BancoDeDados.exe, PreAnaliseXRF.exe e CorretorAgAuRh.exe
rem Precisa do Python instalado so em quem GERA; quem USA o .exe nao
rem precisa de nada.
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller matplotlib numpy pillow openpyxl || goto erro
for %%s in (banco_de_dados pre_analise_xrf corretor_ag_au_rh) do (
    python -m PyInstaller --noconfirm --clean %%s.spec || goto erro
)
echo.
echo Pronto: os executaveis estao na pasta dist\
pause
exit /b 0
:erro
echo.
echo Deu erro ao gerar o executavel (veja as mensagens acima).
pause
exit /b 1

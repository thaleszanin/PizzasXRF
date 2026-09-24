# Receita do PyInstaller para o executável do corretor.
#
# Gera um arquivo só, dist/CorretorAgAuRh.exe, que roda em qualquer Windows sem
# Python instalado. Para gerar:
#
#     pip install pyinstaller openpyxl
#     pyinstaller corretor_ag_au_rh.spec
#
# (ou dê dois cliques em gerar_executavel.bat, que gera os três programas).

a = Analysis(
    ["corretor_ag_au_rh.py"],
    pathex=[],
    binaries=[],
    datas=[],
    # O openpyxl só é importado dentro de funções, então o PyInstaller
    # não o enxerga sozinho.
    hiddenimports=["openpyxl"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Este programa não desenha gráfico nenhum. O numpy e o Pillow são
    # opcionais para o openpyxl, que funciona sem eles.
    excludes=["matplotlib", "numpy", "PIL", "pandas", "scipy", "IPython",
              "jupyter", "notebook", "pytest", "PyQt5", "PyQt6", "PySide2",
              "PySide6", "wx", "gi"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CorretorAgAuRh",
    debug=False,
    strip=False,
    upx=False,
    # Programa de janela: sem o console preto atrás.
    console=False,
)

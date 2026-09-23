# Receita do PyInstaller para o executável do banco de dados.
#
# Gera um arquivo só, dist/BancoDeDados.exe, que roda em qualquer Windows
# sem Python instalado. Para gerar:
#
#     pip install pyinstaller matplotlib numpy pillow openpyxl
#     pyinstaller banco_de_dados.spec
#
# (ou dê dois cliques em gerar_executavel.bat, que faz as duas coisas).

a = Analysis(
    ["banco_de_dados.py"],
    pathex=[],
    binaries=[],
    datas=[],
    # O openpyxl só é importado dentro de funções (é opcional no código),
    # então o PyInstaller não o enxerga sozinho; e o backend do Tk do
    # matplotlib é escolhido em tempo de execução.
    hiddenimports=["openpyxl", "matplotlib.backends.backend_tkagg"],
    hookspath=[],
    hooksconfig={"matplotlib": {"backends": ["TkAgg", "Agg"]}},
    runtime_hooks=[],
    # Nada disso é usado pelo programa; sem essa lista o PyInstaller
    # arrasta o que estiver instalado no Python de quem gera o .exe.
    excludes=["pandas", "scipy", "IPython", "jupyter", "notebook", "pytest",
              "PyQt5", "PyQt6", "PySide2", "PySide6", "wx", "gi"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="BancoDeDados",
    debug=False,
    strip=False,
    upx=False,
    # Programa de janela: sem o console preto atrás.
    console=False,
)

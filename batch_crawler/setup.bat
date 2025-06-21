@echo off
chcp 65001 >nul
echo ========================================
echo  Setup do Batch Crawler MCP
echo ========================================
echo.

:: Verificar se uv esta instalado
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo ERRO: uv nao esta instalado ou nao esta no PATH
    echo.
    echo Para instalar o uv, execute:
    echo   winget install astral-sh.uv
    echo   ou visite: https://docs.astral.sh/uv/getting-started/installation/
    echo.
    pause
    exit /b 1
)

echo [OK] uv encontrado
echo.

:: Remover ambiente virtual existente se houver
if exist ".venv" (
    echo Removendo ambiente virtual existente...
    rmdir /s /q ".venv" 2>nul
    timeout /t 2 /nobreak >nul
)

:: Criar ambiente virtual
echo Criando ambiente virtual...
uv venv .venv
if %errorlevel% neq 0 (
    echo ERRO: Falha ao criar ambiente virtual
    echo.
    echo Possíveis soluções:
    echo   1. Execute como Administrador
    echo   2. Certifique-se de que nenhum processo está usando a pasta .venv
    echo   3. Tente fechar IDEs/editores que possam estar usando arquivos da pasta
    echo   4. Use: rmdir /s /q .venv para remover manualmente
    echo.
    echo Tentando solução alternativa...
    timeout /t 3 /nobreak >nul
    
    :: Tentar com nome alternativo
    echo Tentando criar com nome alternativo...
    uv venv .venv-batch
    if %errorlevel% neq 0 (
        echo ERRO: Ainda não foi possível criar ambiente virtual
        echo Tente executar como Administrador ou feche todos os programas que possam estar usando a pasta
        pause
        exit /b 1
    )
    
    :: Usar ambiente alternativo
    set "VENV_PATH=.venv-batch"
    echo [OK] Ambiente virtual criado em .venv-batch
) else (
    set "VENV_PATH=.venv"
    echo [OK] Ambiente virtual criado em .venv
)

echo.

:: Ativar ambiente virtual e instalar dependencias
echo Ativando ambiente virtual e instalando dependencias...
call %VENV_PATH%\Scripts\activate.bat

echo Instalando dependencias do requirements.txt...
uv pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERRO: Falha ao instalar dependencias
    pause
    exit /b 1
)

echo.
echo [OK] Dependencias instaladas com sucesso!
echo.

:: Verificar instalacoes
echo Verificando instalacoes...
python -c "import httpx, aiofiles; print('[OK] Todas as dependencias estao funcionando')" 2>nul
if %errorlevel% neq 0 (
    echo [AVISO] Algumas dependencias podem nao estar funcionando corretamente
)

echo.
echo ========================================
echo  Setup concluido com sucesso!
echo ========================================
echo.
echo Para usar o batch crawler:
echo   1. Execute start.bat para iniciar o modo interativo
echo   2. Ou use: start.bat [arquivo_urls] [opcoes]
echo.
echo Exemplos:
echo   start.bat
echo   start.bat example_urls.txt
echo   start.bat meus_urls.txt --output resultados.json
echo.
pause
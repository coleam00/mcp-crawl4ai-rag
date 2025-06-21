@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo  Batch Crawler MCP - Modo Interativo
echo ========================================
echo.

:: Verificar se ambiente virtual existe
set "VENV_PATH="
if exist ".venv\Scripts\activate.bat" (
    set "VENV_PATH=.venv"
) else if exist ".venv-batch\Scripts\activate.bat" (
    set "VENV_PATH=.venv-batch"
    echo Usando ambiente virtual alternativo: .venv-batch
) else (
    echo ERRO: Ambiente virtual não encontrado!
    echo.
    echo Execute primeiro o setup.bat para criar o ambiente virtual:
    echo   setup.bat
    echo.
    pause
    exit /b 1
)

:: Ativar ambiente virtual
call %VENV_PATH%\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERRO: Falha ao ativar ambiente virtual
    pause
    exit /b 1
)

echo [OK] Ambiente virtual ativado
echo.

:: Verificar se o servidor MCP esta rodando
echo Verificando conexao com servidor MCP...
python -c "import httpx, asyncio; import sys; resp = asyncio.run(httpx.AsyncClient().get('http://localhost:8051', timeout=5)); sys.exit(0 if resp.status_code in [200, 404, 405] else 1)" >nul 2>nul
if %errorlevel% equ 0 (
    echo [OK] Servidor MCP esta respondendo em http://localhost:8051
) else (
    echo [AVISO] Nao foi possivel conectar ao servidor MCP em http://localhost:8051
    echo   Certifique-se de que o servidor esta rodando antes de continuar.
    echo   Execute: uv run src/crawl4ai_mcp.py (no diretorio principal)
)
echo.

:: Se argumentos foram passados, usar modo direto
if not "%1"=="" (
    echo Executando em modo direto com argumentos: %*
    echo.
    python batch_crawler.py %*
    goto :end
)

:: Modo interativo
:interactive
echo ========================================
echo  Modo Interativo
echo ========================================
echo.
echo Arquivos de URL disponiveis:
echo.

:: Listar arquivos .txt no diretorio
set count=0
for %%f in (*.txt) do (
    set /a count+=1
    set "file!count!=%%f"
    echo   !count!. %%f
)

if !count! equ 0 (
    echo   Nenhum arquivo .txt encontrado no diretorio atual.
    echo.
    goto :manual_input
)

echo.
echo Opcoes:
echo   1-%count%. Selecionar arquivo listado acima
echo   m. Digitar caminho manualmente
echo   e. Usar example_urls.txt
echo   q. Sair
echo.

:input_choice
set /p choice="Escolha uma opcao: "

if /i "%choice%"=="q" goto :end
if /i "%choice%"=="e" (
    set "urls_file=example_urls.txt"
    goto :check_file
)
if /i "%choice%"=="m" goto :manual_input

:: Verificar se eh um numero valido
set "is_number="
for /f "delims=0123456789" %%i in ("%choice%") do set is_number=%%i
if defined is_number (
    echo Opcao invalida. Tente novamente.
    goto :input_choice
)

if %choice% lss 1 (
    echo Opcao invalida. Tente novamente.
    goto :input_choice
)
if %choice% gtr %count% (
    echo Opcao invalida. Tente novamente.
    goto :input_choice
)

:: Selecionar arquivo baseado no numero
call set "urls_file=%%file%choice%%%"
goto :check_file

:manual_input
echo.
set /p urls_file="Digite o caminho do arquivo com URLs: "
if "%urls_file%"=="" (
    echo Caminho invalido.
    goto :input_choice
)

:check_file
if not exist "%urls_file%" (
    echo.
    echo ERRO: Arquivo '%urls_file%' nao encontrado!
    echo.
    goto :input_choice
)

echo.
echo [OK] Arquivo selecionado: %urls_file%
echo.

:: Opcoes avancadas
echo Configuracoes opcionais (pressione Enter para usar padrao):
echo.

set /p output_file="Arquivo de saida [crawl_results.json]: "
if "%output_file%"=="" set "output_file=crawl_results.json"

set /p delay="Delay entre requisicoes em segundos [1]: "
if "%delay%"=="" set "delay=1"

set /p server_url="URL do servidor MCP [http://localhost:8051]: "
if "%server_url%"=="" set "server_url=http://localhost:8051"

echo.
echo ========================================
echo  Configuracao Final
echo ========================================
echo.
echo   Arquivo URLs: %urls_file%
echo   Arquivo saida: %output_file%
echo   Delay: %delay% segundos
echo   Servidor: %server_url%
echo.

set /p confirm="Confirmar e iniciar? [S/n]: "
if /i "%confirm%"=="n" goto :interactive

echo.
echo Iniciando crawling...
echo ========================================
echo.

:: Executar o script que funciona de verdade
python batch_crawler_working.py "%urls_file%" --output "%output_file%" --delay %delay%

echo.
echo ========================================
echo  Crawling concluido!
echo ========================================
echo.

if exist "%output_file%" (
    echo [OK] Resultados salvos em: %output_file%
    echo.
    set /p open_results="Abrir arquivo de resultados? [S/n]: "
    if not "!open_results!"=="n" if not "!open_results!"=="N" (
        start "" "%output_file%"
    )
)

echo.

:repeat
set /p repeat="Processar outro arquivo? [S/n]: "
if /i "%repeat%"=="s" goto :interactive
if /i "%repeat%"=="" goto :interactive

:end
echo.
echo Saindo...
echo.
pause
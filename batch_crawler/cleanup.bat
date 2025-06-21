@echo off
chcp 65001 >nul
echo ========================================
echo  Limpeza de Ambientes Virtuais
echo ========================================
echo.

echo Este script ira remover todos os ambientes virtuais existentes.
echo Isso pode ajudar a resolver problemas de permissao.
echo.

set /p confirm="Deseja continuar? [S/n]: "
if /i "%confirm%"=="n" goto :end

echo.
echo Removendo ambientes virtuais...

:: Tentar fechar processos que podem estar usando arquivos
echo Fechando possíveis processos Python...
taskkill /f /im python.exe 2>nul
taskkill /f /im pythonw.exe 2>nul

timeout /t 2 /nobreak >nul

:: Remover pastas de ambiente virtual
if exist ".venv" (
    echo Removendo .venv...
    rmdir /s /q ".venv" 2>nul
    if exist ".venv" (
        echo Tentando forcar remocao...
        rd /s /q ".venv" 2>nul
    )
    if exist ".venv" (
        echo [AVISO] Nao foi possivel remover .venv completamente
        echo Tente executar como Administrador ou reiniciar o computador
    ) else (
        echo [OK] .venv removido
    )
)

if exist ".venv-batch" (
    echo Removendo .venv-batch...
    rmdir /s /q ".venv-batch" 2>nul
    if exist ".venv-batch" (
        echo Tentando forcar remocao...
        rd /s /q ".venv-batch" 2>nul
    )
    if exist ".venv-batch" (
        echo [AVISO] Nao foi possivel remover .venv-batch completamente
    ) else (
        echo [OK] .venv-batch removido
    )
)

:: Remover arquivos de log antigos
if exist "crawler_*.log" (
    echo Removendo logs antigos...
    del "crawler_*.log" 2>nul
    echo [OK] Logs removidos
)

:: Remover arquivos de resultados antigos (opcional)
set /p remove_results="Remover arquivos de resultados (*.json)? [s/N]: "
if /i "%remove_results%"=="s" (
    if exist "*.json" (
        del "*.json" 2>nul
        echo [OK] Arquivos JSON removidos
    )
)

echo.
echo ========================================
echo  Limpeza concluida!
echo ========================================
echo.
echo Agora voce pode executar setup.bat novamente.

:end
echo.
pause
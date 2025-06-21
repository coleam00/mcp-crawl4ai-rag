@echo off
chcp 65001 >nul
echo ========================================
echo  Teste de Codificacao de Caracteres
echo ========================================
echo.

echo Testando caracteres especiais:
echo [OK] Caracteres normais funcionando
echo [AVISO] Teste de aviso
echo [ERRO] Teste de erro
echo.

echo Testando caracteres acentuados (sem acentos):
echo - configuracao (em vez de configuração)
echo - opcoes (em vez de opções)  
echo - dependencias (em vez de dependências)
echo - conclusao (em vez de conclusão)
echo.

echo Codepage atual: 
chcp
echo.

echo Se voce consegue ler esta mensagem corretamente,
echo a codificacao esta funcionando!
echo.

pause
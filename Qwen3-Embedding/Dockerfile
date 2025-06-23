FROM vllm/vllm-openai:latest

# Instalar dependências adicionais
RUN uv pip install --system transformers>=4.51.0 sentence-transformers>=2.7.0

# Definir variáveis de ambiente
ENV PYTHONPATH=/app
ENV TRANSFORMERS_CACHE=/app/models
ENV HF_HOME=/app/models
ENV VLLM_USE_MODELSCOPE=false

# Criar diretórios necessários
RUN mkdir -p /app/models /app/logs /app/scripts

# Copiar scripts e configurações
COPY scripts/ /app/scripts/
COPY config/ /app/config/
COPY start.sh /app/start.sh

# Dar permissões de execução
RUN chmod +x /app/start.sh /app/scripts/*.sh

# Definir diretório de trabalho
WORKDIR /app

# Expor porta
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando padrão - usar exec form para evitar problemas
CMD ["bash", "/app/start.sh"] 
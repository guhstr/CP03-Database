import os
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env sem sobrescrever as variáveis do sistema/Docker
load_dotenv(override=False)


class Settings:
    PROJECT_NAME: str = "TicketFlash API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "API REST de alta performance para a plataforma de ingressos TicketFlash, utilizando MongoDB para persistência e Redis para cache, reservas temporárias, ranking e rate limiting."

    # MongoDB
    MONGO_URL: str = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    MONGO_DB: str = os.getenv("MONGO_DB", "ticketflash")

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Regras de Negócio e TTLs
    CACHE_TTL: int = int(os.getenv("CACHE_TTL_SEGUNDOS", "60"))            # Req. 5: TTL de 60s para cache de evento
    RESERVA_TTL: int = int(os.getenv("RESERVA_TTL_SEGUNDOS", "600"))       # Req. 6: TTL de 10 minutos (600s)
    LIMITE_RESERVAS: int = int(os.getenv("LIMITE_RESERVAS_POR_MINUTO", "10")) # Req. 8: máx 10 reservas/minuto
    JANELA_LIMITE: int = int(os.getenv("JANELA_LIMITE_SEGUNDOS", "60"))    # Janela de 60 segundos

    # Chaves Redis
    RANKING_KEY: str = "ranking:eventos"
    CANAL_PUB_SUB: str = "pedidos:confirmados"


settings = Settings()

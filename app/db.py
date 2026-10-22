import os
import redis
from pymongo import MongoClient, ASCENDING

# Conexões com MongoDB e Redis utilizando variáveis de ambiente
mongo = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"))
db = mongo[os.getenv("MONGO_DB", "ticketflash")]
r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)


def criar_indices():
    """Req. 3 - Criação dos índices obrigatórios via código na inicialização."""
    # Índice único para garantir que não haja duplicidade de e-mail de usuários
    db.usuarios.create_index([("email", ASCENDING)], unique=True, name="uniq_email")

    # Índice composto para otimizar busca por categoria e ordenação por data
    db.eventos.create_index([("categoria", ASCENDING), ("data", ASCENDING)], name="categoria_data")

    # Índice simples para consultas de pedidos por usuário
    db.pedidos.create_index([("usuarioId", ASCENDING)], name="pedidos_usuario")

    # Índice adicional para acelerar filtro por cidade
    db.eventos.create_index([("local.cidade", ASCENDING)], name="eventos_cidade")

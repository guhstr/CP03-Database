import json
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException
from pymongo import MongoClient, ASCENDING
import redis

from app.config import settings

# Conexão MongoDB
mongo = MongoClient(settings.MONGO_URL)
db = mongo[settings.MONGO_DB]

# Conexão Redis
r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def oid(valor: str) -> ObjectId:
    """Converte uma string para ObjectId do MongoDB com validação."""
    try:
        return ObjectId(valor)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail=f"ID inválido: '{valor}'")


def ser(obj):
    """Converte recursivamente ObjectId e datetime para tipos nativos serializáveis em JSON."""
    if isinstance(obj, dict):
        return {k: ser(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [ser(v) for v in obj]
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def invalidar_cache(evento_id: str):
    """Req. 9: Invalidação de cache no Redis para garantir consistência após alterações."""
    r.delete(f"evento:{evento_id}")


def criar_indices():
    """
    Req. 3 - Criação de índices pelo código na inicialização:
    1. Índice Único em usuarios.email
    2. Índice Composto em eventos (categoria + data)
    3. Índice Simples em pedidos.usuarioId
    4. Índice Adicional em eventos.local.cidade (otimização de filtros)
    """
    db.usuarios.create_index([("email", ASCENDING)], unique=True, name="uniq_email")
    db.eventos.create_index([("categoria", ASCENDING), ("data", ASCENDING)], name="categoria_data")
    db.pedidos.create_index([("usuarioId", ASCENDING)], name="pedidos_usuario")
    db.eventos.create_index([("local.cidade", ASCENDING)], name="eventos_cidade")

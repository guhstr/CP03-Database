from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app.db import db, ser
from app.models import UsuarioCreate

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


@router.post("", status_code=status.HTTP_201_CREATED, summary="Criar novo usuário (com validação de email único)")
def criar_usuario(usuario: UsuarioCreate):
    """
    Cria um novo usuário na coleção 'usuarios'.
    O campo 'email' possui índice único criado na inicialização.
    Se já existir, dispara erro 409 Conflict.
    """
    doc = usuario.model_dump()
    doc["dataCadastro"] = datetime.now(timezone.utc)

    try:
        res = db.usuarios.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail=f"E-mail '{usuario.email}' já cadastrado")

    return {"id": str(res.inserted_id), "mensagem": "Usuário cadastrado com sucesso"}


@router.get("", summary="Listar usuários cadastrados")
def listar_usuarios(limit: int = Query(25, le=100, description="Limite máximo de usuários")):
    """Lista usuários cadastrados no banco."""
    cursor = db.usuarios.find().limit(limit)
    return [ser(u) for u in cursor]

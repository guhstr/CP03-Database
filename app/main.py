from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import db, r, criar_indices
from app.routers import eventos, usuarios, reservas, pedidos, relatorios, admin
from seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida da aplicação: cria índices e popula dados se o banco estiver vazio."""
    # 1. Criação dos índices MongoDB (Req. 3)
    criar_indices()

    # 2. Execução automática do seed caso a base esteja vazia
    if db.eventos.count_documents({}) == 0:
        print("[TicketFlash] Base vazia detectada. Executando seed inicial...")
        seed()
    else:
        print(f"[TicketFlash] Base já populada com {db.eventos.count_documents({})} eventos.")

    yield
    print("[TicketFlash] Encerrando aplicação...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configuração de CORS para flexibilidade de acesso
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro dos roteadores modulares
app.include_router(eventos.router)
app.include_router(usuarios.router)
app.include_router(reservas.router)
app.include_router(pedidos.router)
app.include_router(relatorios.router)
app.include_router(admin.router)


@app.get("/", tags=["Status"], summary="Status e informações da API")
def raiz():
    return {
        "sistema": settings.PROJECT_NAME,
        "status": "online",
        "versao": settings.VERSION,
        "documentacao": "/docs",
        "redoc": "/redoc",
        "endpoints_principais": [
            "/eventos",
            "/eventos/ranking",
            "/usuarios",
            "/reservas",
            "/pedidos/confirmar",
            "/relatorios/faturamento",
            "/relatorios/ocupacao/{evento_id}",
            "/admin/explain"
        ]
    }


@app.get("/health", tags=["Status"], summary="Verificação de integridade dos bancos")
def healthcheck():
    """Verifica a conectividade ativa com MongoDB e Redis."""
    mongo_ok = False
    redis_ok = False

    try:
        db.command("ping")
        mongo_ok = True
    except Exception:
        pass

    try:
        redis_ok = r.ping()
    except Exception:
        pass

    estado = "saudavel" if (mongo_ok and redis_ok) else "degradado"
    return {
        "status": estado,
        "mongo": "conectado" if mongo_ok else "desconectado",
        "redis": "conectado" if redis_ok else "desconectado"
    }

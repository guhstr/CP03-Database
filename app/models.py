from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class Local(BaseModel):
    cidade: str = Field(..., description="Cidade onde ocorrerá o evento", example="São Paulo")
    endereco: str = Field(..., description="Endereço ou local específico", example="Allianz Parque, Av. Francisco Matarazzo, 1705")


class Setor(BaseModel):
    nome: str = Field(..., description="Nome do setor", example="Pista Premium")
    preco: float = Field(..., gt=0, description="Preço unitário do ingresso", example=350.00)
    capacidade: int = Field(..., gt=0, description="Capacidade total de ingressos do setor", example=5000)
    vendidos: int = Field(default=0, ge=0, description="Quantidade de ingressos vendidos")


class EventoCreate(BaseModel):
    nome: str = Field(..., description="Nome do evento", example="Festival Estrela do Rock")
    categoria: str = Field(..., description="Categoria do evento", example="Show")
    data: datetime = Field(..., description="Data e horário do evento", example="2026-11-20T21:00:00")
    local: Local
    atracoes: List[str] = Field(default_factory=list, description="Lista de atrações do evento", example=["Titãs", "CPM 22"])
    setores: List[Setor] = Field(..., min_length=1, description="Lista de setores disponíveis com preços e capacidades")


class EventoUpdate(BaseModel):
    nome: Optional[str] = None
    categoria: Optional[str] = None
    data: Optional[datetime] = None
    local: Optional[Local] = None
    atracoes: Optional[List[str]] = None
    setores: Optional[List[Setor]] = None


class UsuarioCreate(BaseModel):
    nome: str = Field(..., description="Nome completo do usuário", example="Gustavo Sartori")
    email: str = Field(..., description="E-mail único do usuário", example="gustavo.sartori@fiap.com.br")
    cidade: str = Field(..., description="Cidade de residência", example="São Paulo")


class ReservaCreate(BaseModel):
    usuarioId: str = Field(..., description="ID do usuário que realiza a reserva", example="660...abc")
    eventoId: str = Field(..., description="ID do evento desejado", example="660...def")
    setor: str = Field(..., description="Nome do setor escolhido", example="Pista Premium")
    quantidade: int = Field(..., gt=0, le=10, description="Quantidade de ingressos (1 a 10)", example=2)


class PedidoConfirmar(BaseModel):
    usuarioId: str = Field(..., description="ID do usuário que realizou a reserva prévia", example="660...abc")
    eventoId: str = Field(..., description="ID do evento reservado", example="660...def")
    setor: str = Field(..., description="Nome do setor reservado", example="Pista Premium")

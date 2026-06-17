from pydantic import BaseModel


class CountryInfoRequest(BaseModel):
    country_name: str


class CurrencyInfo(BaseModel):
    codigo: str | None
    nome: str | None
    simbolo: str | None


class CountryInfoResponse(BaseModel):
    pais: str
    bandeira: str | None
    capital: list[str]
    idiomas: list[str]
    moedas: list[CurrencyInfo]
    populacao: int | float | None
    fronteiras: list[str]
    area: float | None
    presidente_atual: str | None
    imagem_presidente: str
    personalidades: list[str]
    cultura: str | None
    empresas: list[str]
    tipo_de_governo: str | None

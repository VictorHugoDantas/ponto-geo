"""Funções de georreferenciamento usadas na validação do ponto."""

from math import asin, cos, radians, sin, sqrt

RAIO_TERRA_M = 6_371_000


def distancia_metros(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em metros entre duas coordenadas (fórmula de Haversine)."""
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * RAIO_TERRA_M * asin(sqrt(a))


def local_mais_proximo(lat: float, lon: float, locais):
    """Retorna (local, distancia) do local cadastrado mais próximo, ou (None, None)."""
    melhor, melhor_dist = None, None
    for local in locais:
        d = distancia_metros(lat, lon, local.latitude, local.longitude)
        if melhor_dist is None or d < melhor_dist:
            melhor, melhor_dist = local, d
    return melhor, melhor_dist

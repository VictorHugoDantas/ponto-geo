from types import SimpleNamespace

import pytest

from app.geo import distancia_metros, local_mais_proximo


def test_mesmo_ponto_distancia_zero():
    assert distancia_metros(-15.7939, -47.8828, -15.7939, -47.8828) == 0


def test_distancia_conhecida_brasilia_sao_paulo():
    # Brasília -> São Paulo: ~873 km em linha reta
    d = distancia_metros(-15.7939, -47.8828, -23.5505, -46.6333)
    assert d == pytest.approx(873_000, rel=0.01)


def test_um_grau_de_latitude():
    assert distancia_metros(0, 0, 1, 0) == pytest.approx(111_195, rel=0.001)


def test_local_mais_proximo():
    a = SimpleNamespace(nome="A", latitude=0, longitude=0)
    b = SimpleNamespace(nome="B", latitude=0, longitude=1)
    local, d = local_mais_proximo(0, 0.9, [a, b])
    assert local is b
    assert d == pytest.approx(11_120, rel=0.01)


def test_sem_locais():
    assert local_mais_proximo(0, 0, []) == (None, None)

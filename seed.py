"""Popula o banco com um funcionário e um local de exemplo.

Uso: python seed.py [latitude longitude]
Sem argumentos, usa a Esplanada dos Ministérios (Brasília).
"""

import sys

from sqlmodel import Session, select

from app.database import criar_tabelas, engine
from app.models import Funcionario, Local

lat, lon = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) == 3 else (-15.7939, -47.8828)

criar_tabelas()
with Session(engine) as s:
    if not s.exec(select(Funcionario).where(Funcionario.matricula == "1001")).first():
        s.add(Funcionario(nome="Funcionário Demo", matricula="1001"))
    s.add(Local(nome="Local Demo", latitude=lat, longitude=lon, raio_metros=200))
    s.commit()

print(f"Pronto: matrícula 1001 e local em ({lat}, {lon}) com raio de 200 m.")

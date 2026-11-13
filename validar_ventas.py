"""Validaciones de calidad de datos para el archivo de ventas de AndesMercado.

Cada regla es una función que recibe un DataFrame y devuelve ``None`` si se
cumple, o un mensaje (str) que describe el incumplimiento.

Uso desde la línea de comandos:

    python validar_ventas.py data/ventas.csv

Termina con código de salida 0 si todas las reglas se cumplen y con 1 si alguna
falla, de modo que el orquestador / CI bloquee la carga al data warehouse.
"""

from __future__ import annotations

import sys
from typing import Callable, Optional

import pandas as pd

COLUMNAS_ESPERADAS = ["id_venta", "fecha", "canal", "monto"]
CANALES_VALIDOS = {"tienda", "en_linea"}
MONTO_MAXIMO_VENTA = 5_000_000  # COP, regla de negocio de AndesMercado
FACTOR_MAXIMO_DIARIO = 3  # total diario <= 3 x promedio de los días anteriores

Resultado = Optional[str]


# --------------------------------------------------------------------------- #
# Reglas obligatorias del caso
# --------------------------------------------------------------------------- #
def regla_columnas(df: pd.DataFrame) -> Resultado:
    """El archivo tiene exactamente las columnas id_venta, fecha, canal y monto."""
    columnas = list(df.columns)
    if columnas != COLUMNAS_ESPERADAS:
        return (
            f"columnas: se esperaban {COLUMNAS_ESPERADAS} "
            f"y se recibieron {columnas}"
        )
    return None


def regla_id_venta(df: pd.DataFrame) -> Resultado:
    """id_venta no tiene nulos ni duplicados."""
    if "id_venta" not in df.columns:
        return "id_venta: la columna no existe"
    nulos = int(df["id_venta"].isna().sum())
    duplicados = df.loc[df["id_venta"].duplicated(keep=False) & df["id_venta"].notna(), "id_venta"]
    problemas = []
    if nulos:
        problemas.append(f"{nulos} valor(es) nulo(s)")
    if not duplicados.empty:
        ids = sorted(set(duplicados.tolist()))
        problemas.append(f"duplicados {ids}")
    if problemas:
        return "id_venta: " + "; ".join(problemas)
    return None


def regla_canal(df: pd.DataFrame) -> Resultado:
    """canal solo toma los valores 'tienda' o 'en_linea'."""
    if "canal" not in df.columns:
        return "canal: la columna no existe"
    invalidos = df.loc[~df["canal"].isin(CANALES_VALIDOS), "canal"]
    if not invalidos.empty:
        valores = sorted(set(map(str, invalidos.tolist())))
        return f"canal: valores no permitidos {valores} (permitidos: {sorted(CANALES_VALIDOS)})"
    return None


def regla_monto_maximo(df: pd.DataFrame) -> Resultado:
    """Ninguna venta individual supera COP 5.000.000."""
    if "monto" not in df.columns:
        return "monto: la columna no existe"
    monto = pd.to_numeric(df["monto"], errors="coerce")
    excedidas = df.loc[monto > MONTO_MAXIMO_VENTA]
    if not excedidas.empty:
        ids = excedidas["id_venta"].tolist() if "id_venta" in df.columns else excedidas.index.tolist()
        return (
            f"monto_maximo: {len(excedidas)} venta(s) superan COP {MONTO_MAXIMO_VENTA:,.0f} "
            f"(id_venta {ids})"
        )
    return None


def regla_total_diario(df: pd.DataFrame) -> Resultado:
    """El total diario por canal no supera 3 veces el promedio de los días anteriores.

    El primer día de cada canal no tiene historia y por eso no se evalúa.
    """
    requeridas = {"fecha", "canal", "monto"}
    if not requeridas.issubset(df.columns):
        return f"total_diario: faltan columnas {sorted(requeridas - set(df.columns))}"

    datos = df.assign(
        fecha=pd.to_datetime(df["fecha"], errors="coerce"),
        monto=pd.to_numeric(df["monto"], errors="coerce"),
    ).dropna(subset=["fecha", "monto"])
    totales = datos.groupby(["canal", "fecha"])["monto"].sum().sort_index()

    alertas = []
    for canal, serie in totales.groupby(level="canal"):
        serie = serie.droplevel("canal")
        promedio_previo = serie.expanding().mean().shift(1)
        for fecha, total in serie.items():
            previo = promedio_previo.loc[fecha]
            if pd.notna(previo) and total > FACTOR_MAXIMO_DIARIO * previo:
                alertas.append(
                    f"{canal} {fecha.date()} total {total:,.0f} > "
                    f"{FACTOR_MAXIMO_DIARIO}x promedio previo {previo:,.0f}"
                )
    if alertas:
        return "total_diario: " + "; ".join(alertas)
    return None


# --------------------------------------------------------------------------- #
# Reglas adicionales (no exigidas, pero recomendadas por el contrato de datos)
# --------------------------------------------------------------------------- #
def regla_tipos(df: pd.DataFrame) -> Resultado:
    """fecha es una fecha ISO válida y monto es numérico y mayor que cero."""
    problemas = []
    if "fecha" in df.columns:
        fechas = pd.to_datetime(df["fecha"], format="%Y-%m-%d", errors="coerce")
        if fechas.isna().any():
            problemas.append(f"{int(fechas.isna().sum())} fecha(s) inválida(s)")
    if "monto" in df.columns:
        monto = pd.to_numeric(df["monto"], errors="coerce")
        if monto.isna().any():
            problemas.append(f"{int(monto.isna().sum())} monto(s) no numérico(s)")
        if (monto <= 0).any():
            problemas.append(f"{int((monto <= 0).sum())} monto(s) <= 0")
    if problemas:
        return "tipos: " + "; ".join(problemas)
    return None


REGLAS: list[Callable[[pd.DataFrame], Resultado]] = [
    regla_columnas,
    regla_id_venta,
    regla_canal,
    regla_monto_maximo,
    regla_total_diario,
    regla_tipos,
]


def validar(df: pd.DataFrame) -> list[str]:
    """Ejecuta todas las reglas y devuelve la lista de reglas incumplidas."""
    incumplidas = []
    for regla in REGLAS:
        mensaje = regla(df)
        if mensaje:
            incumplidas.append(mensaje)
    return incumplidas


def cargar(ruta: str) -> pd.DataFrame:
    """Lee el CSV conservando los valores como texto para no ocultar errores de tipo."""
    return pd.read_csv(ruta, dtype={"id_venta": "Int64", "fecha": str, "canal": str, "monto": str})


def main(argv: list[str]) -> int:
    ruta = argv[1] if len(argv) > 1 else "data/ventas.csv"
    df = cargar(ruta)
    incumplidas = validar(df)

    print(f"Validando {ruta} ({len(df)} filas, {len(REGLAS)} reglas)")
    if incumplidas:
        print(f"\nFALLÓ: {len(incumplidas)} regla(s) incumplida(s). Se bloquea la carga.\n")
        for mensaje in incumplidas:
            print(f"  ✗ {mensaje}")
        return 1
    print("\nOK: todas las reglas se cumplen. La carga puede continuar.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

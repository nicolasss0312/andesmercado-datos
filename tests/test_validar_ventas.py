"""Pruebas de validar_ventas.py: un caso válido y al menos un caso inválido por regla."""

from pathlib import Path

import pandas as pd
import pytest

import validar_ventas as vv

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def df_valido() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id_venta": [1, 2, 3, 4, 5, 6],
            "fecha": ["2025-11-25", "2025-11-25", "2025-11-26", "2025-11-26", "2025-11-27", "2025-11-27"],
            "canal": ["tienda", "en_linea", "tienda", "en_linea", "tienda", "en_linea"],
            "monto": [100000.0, 200000.0, 120000.0, 210000.0, 110000.0, 190000.0],
        }
    )


# --------------------------- caso válido ----------------------------------- #
def test_datos_validos_pasan_todas_las_reglas(df_valido):
    assert vv.validar(df_valido) == []


@pytest.mark.parametrize("regla", vv.REGLAS, ids=lambda r: r.__name__)
def test_cada_regla_acepta_datos_validos(regla, df_valido):
    assert regla(df_valido) is None


# --------------------------- regla 1: columnas ------------------------------ #
def test_columnas_falta_una(df_valido):
    assert vv.regla_columnas(df_valido.drop(columns=["canal"])) is not None


def test_columnas_sobra_una(df_valido):
    assert vv.regla_columnas(df_valido.assign(moneda="COP")) is not None


def test_columnas_nombre_distinto(df_valido):
    assert vv.regla_columnas(df_valido.rename(columns={"monto": "monto_centavos"})) is not None


# --------------------------- regla 2: id_venta ------------------------------ #
def test_id_venta_con_nulo(df_valido):
    df = df_valido.astype({"id_venta": "Int64"})
    df.loc[0, "id_venta"] = pd.NA
    assert "nulo" in vv.regla_id_venta(df)


def test_id_venta_duplicado(df_valido):
    df = df_valido.copy()
    df.loc[1, "id_venta"] = 1
    assert "duplicados" in vv.regla_id_venta(df)


# --------------------------- regla 3: canal --------------------------------- #
def test_canal_no_permitido(df_valido):
    df = df_valido.copy()
    df.loc[0, "canal"] = "online"
    assert "online" in vv.regla_canal(df)


# --------------------------- regla 4: monto máximo -------------------------- #
def test_monto_supera_cinco_millones(df_valido):
    df = df_valido.copy()
    df.loc[1, "monto"] = 5_000_001
    assert vv.regla_monto_maximo(df) is not None


def test_monto_igual_al_limite_es_valido(df_valido):
    df = df_valido.copy()
    df.loc[1, "monto"] = 5_000_000
    assert vv.regla_monto_maximo(df) is None


# --------------------------- regla 5: total diario -------------------------- #
def test_total_diario_triplica_promedio(df_valido):
    df = df_valido.copy()
    # en_linea: promedio de 25 y 26 = 205.000 -> límite 615.000
    df.loc[5, "monto"] = 700000.0
    mensaje = vv.regla_total_diario(df)
    assert mensaje is not None and "en_linea" in mensaje


def test_total_diario_primer_dia_no_se_evalua():
    df = pd.DataFrame(
        {"id_venta": [1], "fecha": ["2025-11-25"], "canal": ["tienda"], "monto": [4_000_000.0]}
    )
    assert vv.regla_total_diario(df) is None


# --------------------------- regla adicional: tipos ------------------------- #
def test_tipos_monto_negativo(df_valido):
    df = df_valido.copy()
    df.loc[0, "monto"] = -10
    assert vv.regla_tipos(df) is not None


def test_tipos_fecha_invalida(df_valido):
    df = df_valido.astype({"fecha": object})
    df.loc[0, "fecha"] = "28/11/2025"
    assert vv.regla_tipos(df) is not None


# --------------------------- archivos reales -------------------------------- #
def test_anexo_detecta_incidente_black_friday():
    incumplidas = vv.validar(vv.cargar(DATA / "ventas_anexo.csv"))
    texto = " ".join(incumplidas)
    assert any(m.startswith("monto_maximo") for m in incumplidas)
    assert any(m.startswith("total_diario") for m in incumplidas)
    assert "1012" in texto and "1013" in texto and "1014" in texto
    assert "en_linea 2025-11-28" in texto


def test_datos_corregidos_pasan():
    assert vv.validar(vv.cargar(DATA / "ventas_corregido.csv")) == []


def test_main_devuelve_1_si_falla_y_0_si_pasa():
    assert vv.main(["validar_ventas.py", str(DATA / "ventas_anexo.csv")]) == 1
    assert vv.main(["validar_ventas.py", str(DATA / "ventas_corregido.csv")]) == 0

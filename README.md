# AndesMercado · Validación de calidad de datos de ventas

Repositorio del caso *DevOps en la arquitectura de datos de AndesMercado* (Arquitectura de Software, Universidad EAN).

Implementa un *quality gate*: antes de cargar `ventas.csv` al data warehouse se ejecutan reglas de calidad; si alguna falla, el script termina con código de salida `1` y el flujo de CI/CD bloquea la carga.

## Estructura

```
validar_ventas.py              # Una función por regla + validar(df) + script CLI
tests/test_validar_ventas.py   # Pruebas pytest (caso válido + casos inválidos por regla)
data/ventas.csv                # Archivo que valida el CI
data/ventas_anexo.csv          # Datos del anexo tal como llegaron (incidente)
data/ventas_corregido.csv      # Datos del 28-nov convertidos de centavos a pesos
.github/workflows/ci.yml       # GitHub Actions: pruebas -> validación de datos
requirements.txt
```

## Reglas implementadas

| # | Función | Regla |
|---|---------|-------|
| 1 | `regla_columnas` | Exactamente las columnas `id_venta, fecha, canal, monto` |
| 2 | `regla_id_venta` | `id_venta` sin nulos ni duplicados |
| 3 | `regla_canal` | `canal` ∈ {`tienda`, `en_linea`} |
| 4 | `regla_monto_maximo` | Ninguna venta supera COP 5.000.000 |
| 5 | `regla_total_diario` | Total diario por canal ≤ 3 × promedio de los días anteriores |
| + | `regla_tipos` | `fecha` en formato ISO y `monto` numérico > 0 (adicional, del contrato de datos) |

`validar(df)` devuelve la lista de reglas incumplidas (lista vacía = datos válidos).

## Cómo ejecutarlo

Requiere Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

pytest -v                                      # pruebas
python validar_ventas.py data/ventas.csv       # valida un archivo
echo $?                                        # 1 = bloquea la carga, 0 = OK
```

## Integración continua

En cada `push` o `pull_request`, GitHub Actions ejecuta dos jobs en secuencia:

1. **Pruebas de código** (`pytest`). Si fallan, no se validan datos.
2. **Validar ventas.csv**. Si `validar_ventas.py` sale con código 1, el job queda en rojo y la carga simulada no se ejecuta.

También se puede lanzar a mano (*Actions → Run workflow*) indicando otro archivo, por ejemplo `data/ventas_anexo.csv`.

## Resultado sobre el anexo

```
$ python validar_ventas.py data/ventas_anexo.csv
Validando data/ventas_anexo.csv (15 filas, 6 reglas)

FALLÓ: 2 regla(s) incumplida(s). Se bloquea la carga.

  ✗ monto_maximo: 3 venta(s) superan COP 5,000,000 (id_venta [1012, 1013, 1014])
  ✗ total_diario: en_linea 2025-11-28 total 73,970,050 > 3x promedio previo 473,667
```

Dos reglas detectan el incidente del 28 de noviembre: el **monto máximo por venta** (las ventas 1012, 1013 y 1014 llegaron en centavos) y el **total diario por canal** (73,97 M frente a un promedio previo de 0,47 M, unas 156 veces). Con este control en el pipeline, la carga de las 2:00 a.m. se habría bloqueado y el error **no habría llegado al tablero** de Power BI; el equipo habría recibido una alerta en lugar de que la gerencia tomara la decisión de compra de COP 850 millones.

Las reglas de columnas, `id_venta` y `canal` no detectan este incidente porque el cambio fue de **unidades**, no de estructura; por eso el contrato de datos debe declarar la unidad de `monto`.

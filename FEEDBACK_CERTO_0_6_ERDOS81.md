# Feedback de Certo 0.6 desde la formalización de Erdős #81

**Fecha:** 17-sep-2026  
**Versión probada:** Certo 0.6.0, commit `c54ab69`  
**Caso de uso:** selección mixta K3/K4, cuotas por tipo, cobertura física y
certificación de optimalidad en la ruta RC01 de Paper IV.

## Resumen ejecutivo

Certo 0.6 ya es genuinamente útil como capa de auditoría matemática. En estas
pruebas produjo:

- óptimos LP racionales con dual exacto y verificación sin solver;
- un certificado paramétrico válido para una familia infinita de desigualdades;
- certificados de cobertura exacta por conteo;
- un árbol branch-and-bound que prueba un óptimo entero, no sólo un incumbent;
- procedencia, hash de la spec y ledger reproducible.

Las mejoras respecto del prototipo anterior son sustantivas: la aritmética
exacta, la procedencia y la salida esparsa ya resuelven tres de los problemas
principales detectados anteriormente.

Los dos problemas funcionales prioritarios son:

1. `mixed` emite un certificado inválido cuando todas las variables son
   discretas y no queda LP residual;
2. `--prove-optimal` no normaliza minimización y el timeout no actúa como un
   presupuesto global de la búsqueda.

## 1. Resultados positivos reproducibles

### 1.1 Óptimo LP exacto: PASS

La relajación de cobertura exacta K2/K3/K4 de K8 produjo

```text
EXACT optimum certified: 14/3
certificate: lp_dual (no solver needed, id a05fe7485c64991d)
```

`certo verify` comprueba factibilidad primal y dual y dualidad fuerte en
`Fraction`, sin tolerancias. Éste es exactamente el tipo de artefacto que se
puede citar y posteriormente traducir a Lean.

### 1.2 `mixed --prove-optimal`: PASS en una celda pequeña

Para el packing físico mixto K3/K4 de K6:

```text
OPTIMUM 8, PROVED: 63 nodes, 32 of them closed by a certificate
```

El verificador confirma:

- incumbent de valor 8;
- ningún nodo duplicado;
- ningún hijo faltante;
- todas las hojas cerradas;
- árbol completo de 63 nodos.

Este comando agrega valor real: distingue una construcción encontrada de una
construcción globalmente óptima. En este ejemplo también exhibe un déficit
integral fuerte frente al valor fraccional `25/2`.

### 1.3 `cover`: PASS solver-free

Una partición explícita de K8 formada por tres triángulos, dos K4 y siete K2
fue certificada como una cobertura exacta de las 28 aristas:

```text
an EXACT COVER: 12 parts, every one of the 28 elements in exactly one
```

La comprobación por conteo es pequeña, transparente y completamente adecuada
para validar la salida física de un constructor matemático.

### 1.4 `parametric`: PASS solver-free

La combinación de dos cuotas se certificó para todo `p >= 1`, con cota

```text
-30/7*p^2 - 12/7*p
```

mediante dualidad débil. Éste es probablemente el byproduct más valioso para
formalización: Certo encuentra o valida el multiplicador, mientras Lean recibe
una identidad algebraica pequeña.

## 2. Bug P0: certificado inválido cuando el modelo es totalmente discreto

### Reproducción

```powershell
certo mixed research\certo06_rc01_kn8_beta_two_sevenths.py `
  --target 15 `
  --cert research\certo06_rc01_kn8_beta_two_sevenths.cert.json

certo verify research\certo06_rc01_kn8_beta_two_sevenths.cert.json
```

La búsqueda encuentra correctamente un punto entero factible de valor 16. El
verificador confirma que el punto es integral, satisface las 30 restricciones,
alcanza el valor declarado y supera el target. Sin embargo termina en:

```text
[XX] and that residual IS the original problem with this assignment substituted
```

Las 126 variables son discretas. Después de congelarlas, el residual tiene cero
variables. El certificado representa ese residual de forma distinta de la que
el verificador espera.

### Comportamiento esperado

Si no quedan variables continuas, hay dos soluciones limpias:

1. emitir un certificado específico `discrete_design`, que sólo compruebe la
   asignación completa, restricciones, objetivo y target; o
2. canonicalizar el LP residual vacío de la misma manera en productor y
   verificador.

No debería emitirse como válido un artefacto que el propio `verify` rechaza.
Idealmente `mixed` debería auto-verificar el certificado antes de escribir un
veredicto concluyente en el ledger.

## 3. Bug P1: `--prove-optimal` sólo acepta maximización

Para una partición mínima natural:

```text
out_of_theory:
--prove-optimal handles maximisation; negate the objective for a minimisation
```

La transformación es exacta y mecánica. La CLI debería:

1. negar internamente el objetivo;
2. ejecutar branch-and-bound como maximización;
3. devolver en el certificado y en pantalla el mínimo con el signo original.

Obligar al usuario a modificar la spec hace más fácil confundir signos y deja
el certificado describiendo una formulación distinta de la matemática que se
quiere citar.

## 4. Timeout de branch-and-bound: semántica confusa

Una ejecución con

```text
--timeout-ms 240000 --max-nodes 20000
```

continuó durante más de nueve minutos en el modelo K8 de dos cuotas. Esto
sugiere que `--timeout-ms` limita llamadas individuales al solver y no el tiempo
de pared de toda la búsqueda.

Propuesta:

- añadir `--wall-timeout-ms` como presupuesto global estricto;
- reservar `--node-timeout-ms` para cada relajación, si ésa es la semántica
  actual;
- al agotarse, devolver `unknown/resource_limit`, preservando incumbent,
  mejor bound, número de nodos y gap, pero sin certificado de optimalidad.

El comportamiento debe quedar explícito en `--help`.

## 5. Bug P1: precio dual de cargas `>=` mostrado como cero

En el test de cuotas locales de K8, el certificado exacto contiene

```text
quota_K4_geq : dual 1
```

pero el informe de cargas muestra dual cero para `quota_K4`. La fila se renombra
con sufijo `_geq` al normalizar a `<=`, mientras el reporter consulta el nombre
anterior.

La factibilidad, el slack y el carácter binding son correctos; falla solamente
la asociación del shadow price. Conviene mantener un mapa explícito
`original_name -> normalized_rows` y restaurar signo y nombre al informar.

## 6. Integración propuesta: `cover --optimize`

Hoy `cover` y `opt` responden preguntas distintas y hay que reconstruir el LP
manualmente:

- `cover` certifica que una lista dada cubre exactamente el universo;
- `opt` calcula el óptimo de una relajación escrita aparte.

Sería valioso añadir una conversión canónica:

```python
CoverSpec.to_lp(integral=False)  # relajación fraccional
CoverSpec.to_lp(integral=True)   # cobertura física mínima
```

y, opcionalmente:

```text
certo cover spec.py --optimize --prove-optimal
```

El bundle podría contener:

1. el certificado `exact_cover` del incumbent;
2. el dual de la relajación;
3. cuando termine, el árbol branch-and-bound del óptimo entero;
4. si no termina, incumbent, lower bound y gap claramente etiquetados como no
   concluyentes.

Esto evitaría que el usuario interprete erróneamente una cobertura válida como
óptima o el óptimo fraccional como coste integral.

## 7. Certificados branch-and-bound: tamaño y dependencia del solver

El certificado del ejemplo K6 ocupa aproximadamente 842 KB para 63 nodos y se
marca `solver_free: false`. Es correcto que la herramienta no prometa más de lo
que verifica, pero convendría documentar:

- qué parte requiere solver durante `verify`;
- si cada hoja guarda un dual/Farkas exacto;
- si es posible un modo `--fully-checkable` más grande pero solver-free;
- estadísticas de tamaño por tipo de hoja.

Una compresión estructural simple —heredar bounds y decisiones desde el padre
en vez de repetir el estado— podría ser significativa en árboles medianos.

## 8. Ergonomía y auditoría

### 8.1 `certo --version`

Actualmente se interpreta como ausencia de subcomando. Debería imprimir al
menos versión, commit si está disponible y schema máximo de certificado.

### 8.2 Verificación opcional contra la spec actual

El certificado ya guarda `spec_path` y `spec_sha256`, lo que es excelente. Una
opción

```text
certo verify cert.json --spec spec.py
```

podría fallar si el hash no coincide. Esto evita verificar correctamente un
certificado antiguo creyendo que corresponde al fichero actualmente visible.

### 8.3 Auto-verificación al emitir certificados

Para certificados baratos, o bajo `--self-check`, el comando productor debería
invocar inmediatamente el mismo checker de `verify`. Habría detectado el bug
del residual totalmente discreto antes de registrar un PASS aparente.

## 9. Escala de uso recomendada

Los experimentos delimitan bien el papel de Certo:

| tarea | valoración |
|---|---|
| LP racional y extracción dual | excelente |
| desigualdades paramétricas lineales | excelente |
| validar una cobertura física | excelente |
| optimalidad entera en cámaras pequeñas | útil |
| MILP sin cocientar con cientos de binarias | exploratorio/caro |
| teorema asintótico universal | fuera de alcance, correctamente |

Para Erdős #81 usaríamos `mixed --prove-optimal` después de reducción por
simetría u órbitas, y `cover` para validar el output físico. La existencia
universal del selector sigue necesitando una demostración matemática; Certo
sirve para refutar candidatos, descubrir excepciones, calibrar constantes y
certificar las obligaciones finitas.

## 10. Prioridad sugerida

| prioridad | cambio | razón |
|---|---|---|
| P0 | corregir residual vacío de `mixed` | hoy se emite un certificado que `verify` rechaza |
| P0 | auto-verificación opcional al producir | impide registrar certificados internamente inválidos |
| P1 | soportar minimización en branch-and-bound | transformación mecánica, elimina errores de signo |
| P1 | timeout global y salida parcial honesta | hace controlable la búsqueda exponencial |
| P1 | corregir nombres/duales de cargas `>=` | el precio dual es información matemática central |
| P2 | `CoverSpec.to_lp` / `cover --optimize` | integra construcción, relajación y optimalidad |
| P2 | `verify --spec` y `--version` | mejora procedencia y reproducibilidad |
| P3 | certificado B&B compacto/solver-free | necesario para instancias medianas y archivo a largo plazo |

## Artefactos de la prueba

Los modelos, certificados y ledger están en:

```text
C:\Users\jtraverso\e81p4\preprints\PAPER_IV\05_formalization\lean\research
```

El informe matemático complementario es:

```text
C:\Users\jtraverso\e81p4\preprints\PAPER_IV\05_formalization\lean\docs\
CERTO06_RC01_TWO_QUOTA_AUDIT_20260917.md
```

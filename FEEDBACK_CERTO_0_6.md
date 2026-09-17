# Feedback sobre certo 0.6.0

**Contexto:** uso real en una formalización Lean 4 / Mathlib de un problema de partición en
cliques (Erdős #81 / Paper V). Todo lo de abajo son comandos que corrí, no impresiones.

---

## 1. Lo que hizo, medido

En esta sesión certo **corrigió cuatro conclusiones mías antes de que salieran de la máquina**:

| lo que yo afirmaba | comando | veredicto | tiempo |
|---|---|---|---|
| «la restricción de densidad obliga a `G` casi completo ⟹ trivial» | `prove` | **REFUTED**, `dens = 27/32` | 15 ms |
| «con `\|κ\| ≥ 4` el objetivo se alcanza en toda densidad» | `prove` | **REFUTED**, `dens = 127/128`, `κ=7` | 9 ms |
| gap de integralidad 0 en la familia split | `opt --gap` | **CONDITIONAL OPTIMUM** — el aviso me mandó a `mixed` | — |
| una partición en cliques que construí | `cover` → `opt` | el mensaje de `cover` destapó que mi construcción era mala | 1.4 ms |

Las dos primeras las habría mandado a un demostrador automático. En este proyecto eso son dos
ciclos de ~2,5 h que no se quemaron.

## 2. Los comandos nuevos, uno por uno

### `parametric` — el mejor añadido de 0.6

```
PROVED  [unsat]
  for all n >= 2, the optimum is at most 5/12*n^2 - 5/12*n
  and that is every value with n >= 2 -- not a sample of them
```

0,2 ms, sin solver. Certifica **de una vez para todo `n`** una cota que yo tenía demostrada en
Lean para todo `n` por otra vía: verificación cruzada independiente y gratis.

El reparto de trabajo —*el dual es entrada, comprobarlo es aritmética*— es correcto y está bien
documentado. Y el aviso de que el test es **suficiente y no necesario**, con el ejemplo
`p²−3p+3` que lo falla siendo positivo, es exactamente la clase de honestidad que hace la
herramienta usable.

**Fricción real:** el docstring de `ParametricSpec` muestra

```python
objective={"x": one, "y": p - 5}
```

que se lee como términos z3. Pasé `z3.RealVal(...)` y obtuve

```
error: TypeError: argument should be a string or a Rational instance
```

sin decir **qué argumento** ni que esperaba `Poly`. Tuve que abrir `examples/parametric_bound.py`
para descubrir `Poly.var` / `Poly.const`. **El docstring y el tipo aceptado no coinciden.**
Arreglo barato: poner `Poly` en el ejemplo del docstring, o aceptar términos z3 y convertirlos.

### `mixed --prove-optimal` — convierte condicional en probado

```
PROVED  OPTIMUM 28, PROVED: 1 nodes, 1 of them closed by a certificate
  1 nodes: 1 closed by bound, 0 infeasible, 0 fully fixed
```

Cuatro instancias pasaron de «óptimo condicional al esqueleto» a **óptimo probado**, todas
cerrando en 1 nodo por cota dual exacta. El desglose por razón de cierre (cota / Farkas /
fijadas) es útil de verdad, no decorativo.

**Lo que echo en falta:** tres de siete instancias volvieron `INCONCLUSIVE` **sin información
parcial**. Un branch and bound que se corta tiene siempre algo que decir: mejor incumbente,
mejor cota, nodos explorados. Con eso yo habría sabido si estaba cerca o lejos; sin eso, la
instancia es un agujero.

### `cover` — y el mensaje que vale más que el comando

```
PROVED  an EXACT COVER: 155 parts, every one of the 245 elements in exactly one
  this is the upper bound. `opt` on the same universe gives the exact dual,
  and where the two meet the size is proved minimum
```

Verificó que cada parte fuera clique de verdad y cubriera cada arista exactamente una vez. Pero
**lo decisivo fue la última línea**: me llevó a `opt`, y al hacerlo descubrí que mi construcción
era mala —daba 780 partes donde la obvia da ~41— y que el «peor caso» que había encontrado era
un artefacto mío, no una propiedad del grafo. Sin ese mensaje habría reportado un artefacto como
hallazgo.

### `lint` — mi petición de 0.5, funcionando

Escribí `s.claim(z3.BoolVal(True))` y:

```
[!!] the claim is the literal True, so there is nothing to prove;
     `certo check --hypotheses-only` asks about the hypotheses and says so in the verdict
```

Cazó el error **y nombró el comando exacto**. `--hypotheses-only` también está y funciona. Los
dos ítems que reporté en 0.5 llegaron en 0.5.1 y siguen bien en 0.6.

### `eliminate` — el nombre invita a la expectativa equivocada

Es el **resultante de exactamente dos polinomios**: eliminación algebraica. Por el nombre esperé
eliminación de cuantificadores sobre desigualdades, que es lo que necesitaba (despejar una
variable de un sistema de `≤`). El docstring lo aclara en la primera línea, pero el
`--help` de una línea no. Sugerencia: que el help diga «resultant of two polynomials», o
renombrarlo `resultant`. No lo forcé donde no encajaba.

## 3. Fricciones menores

1. **`INCONCLUSIVE [timeout]` dice `canceled`**, que se lee como si lo hubiera cancelado yo.
2. **Sin pista de reducción en el timeout.** `prove` sobre una desigualdad con `n⁶` simbólico se
   fue a timeout en 10 s; dividiendo yo el `n⁶` común resolvió en **12 ms**. Una línea del tipo
   «try factoring common powers» ahorraría el ciclo.
3. **`opt --gap --by-type`**: pasé `--by-type` y no vi desglose por tipo en la salida. O mis
   `kind` estaban mal puestos o el desglose se suprime cuando también va `--gap`; no quedó claro.
4. **Dos formas del certificado** (reportado en 0.5, sigue): `--cert FILE` escribe
   `{schema, kind, …, payload}` en la raíz; `--json` lo anida bajo `certificate`.

## 4. La petición que repito, ahora más afilada

**Sigue sin haber modo de escalado asintótico, y es mi clase de error más cara.**

En este proyecto, cuatro veces un régimen de parámetros resultó ser `Θ(1)` en `n` en vez de
`Θ(1/n)`: factible, pero que **no mejora al crecer `n`**. Eso es invisible para las tres
herramientas a la vez:

* Lean lo demuestra sin protestar —el teorema es cierto y vacío—;
* `#print axioms` sale limpio;
* `prove` dice SAT, porque no es infactibilidad.

Lo que lo caza: tomar una expresión más una asignación de órdenes (`d ↦ n²`, `C ↦ n`,
`W ↦ n²`) y devolver **el exponente de `n`** con certificado. Lo hice a mano con Python tres
veces esta sesión. `bounds` es intervalos numéricos con Arb, otra cosa.

Si tuviera que pedir una sola función para 0.7, sería ésa.

## 5. Una observación de diseño

El mejor rasgo de certo no es que resuelva: es que **no para de decir qué NO ha demostrado**.
`VACUOUS`, `CONDITIONAL OPTIMUM`, «suficiente y no necesario», «this is the upper bound», el
`lint` que nombra el comando correcto. Cuatro veces esta sesión eso corrigió una conclusión mía.

Es una propuesta de valor distinta de «te resuelvo el problema», y creo que debería ser el
titular del README, no un detalle que se descubre usándolo.

## 6. Alcance de este feedback

Todo lo probado fue aritmética real no lineal con 6–14 variables, LPs de hasta ~1000 columnas, y
branch and bound de hasta 20 000 nodos. **No lo he estresado.** Sin opinión sobre `sweep`,
`induct`, `sos`, `ideal`, `synth` ni los motores SAT, que no usé.

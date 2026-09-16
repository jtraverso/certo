# certo

> Traducción al español. La versión de referencia es [README.md](README.md).

Laboratorio de apoyo a demostraciones matemáticas, por CLI y por MCP.
**Todo resultado viene con un certificado que se verifica sin confiar en el solver.**

Dieciséis comandos para descubrir objetos, destruir formulaciones falsas, calibrar
constantes y minimizar hipótesis — antes de pagar el coste de formalizar.

```
$ certo bisect examples/bisect_ramsey.py
UMBRAL ACOTADO por demostracion y refutacion  [sat]
  umbral en 6 (se cumple en t=6, falla en t=5; 4 pruebas)

$ certo verify out/r33.json
VALIDO  certificado bisect (verificado sin solver)
  [ok] lado bueno t=6 (drat)        (23 pasos RUP)
  [ok] lado malo  t=5 (cnf_model)
```

## Qué es y qué no es

**Es** el instrumento de laboratorio: encontrar una contradicción rápido, saber
qué hipótesis sobran, validar exhaustivamente un caso finito, acotar una
constante con certificado, sintetizar un candidato sobre un dominio acotado.

**No es** un asistente de demostración — eso es Lean, Rocq o Isabelle — ni un
catálogo de cálculo simbólico. Ver [Qué no hace](#qué-no-hace), que es tan
importante como la lista de comandos.

## Instalación

Requiere Python 3.11+.

```bash
pip install -e ".[mcp,numerics]"
```

Dependencias: `z3-solver` y `pulp`, que traen sus propios binarios. Los extras
son `mcp` para el servidor MCP y `numerics` para `bounds` (`python-flint` y
`mpmath`); sin ellos queda el CLI, menos la numérica rigurosa.

Comprueba que funciona:

```bash
python tests/test_smoke.py && python tests/test_mcp.py
```

### Opcionales

| Herramienta | Para qué | Sin ella |
|---|---|---|
| [`nauty`](https://pallini.di.uniroma1.it/) (`geng` en el `PATH`) | enumerar grafos | motor Python, cómodo hasta n=8 |
| `cadical` o `kissat` | `cases` en instancias grandes | CDCL propio, correcto pero lento |
| `drat-trim` | segunda opinión sobre las pruebas DRAT | el verificador propio en Python basta |
| `python-flint` (Arb) | `bounds` con funciones especiales | `mpmath.iv`, para las elementales |

Ninguna se instala automáticamente y ninguna hace falta para empezar.

## Empezar en dos minutos

```bash
certo --help
```

```bash
certo core examples/amgm.py
```

```
DEMOSTRADO -- simbolico y universal bajo las hipotesis  [unsat]
  hipotesis necesarias: a_pos, b_pos, c_pos | superfluas: ruido
```

Cada fichero de [`examples/`](examples/) lleva en su docstring qué hace y qué
esperar.

## Las tres reglas transversales

1. **Todo comando devuelve un certificado, o dice explícitamente por qué no.**
   Nunca un "sí" desnudo.
2. **Seis estados de resultado:** `unsat`, `sat`, `unknown_solver`,
   `timeout`, `resource_exhausted`, `out_of_theory`. Solo los dos primeros
   son concluyentes. Los otros cuatro significan «no hay respuesta», pero por
   motivos distintos, y confundirlos cuesta caro: un LLM que lee «unknown»
   escribe «no existe solución».
3. **Determinismo por presupuesto de trabajo, no por reloj:** `rlimit` en Z3 y
   `conflict_budget` en SAT. *Esto cubre los motores propios, no tu predicado:*
   si tu predicado de `sweep` llama a scipy o a CBC, esa parte queda fuera.

## Los dieciséis comandos

| Comando | Qué hace | Motor | Certificado |
|---|---|---|---|
| `prove` | Niega la tesis y busca `unsat` | Z3 | núcleo insatisfacible, o contraejemplo |
| `check` | Satisfacibilidad directa | Z3 | modelo, o núcleo |
| `core` | MUS: qué hipótesis hacen falta | Z3 | núcleo minimal |
| `farkas` | `linarith` / `nlinarith`, con los multiplicadores | LP exacto | **certificado de Farkas**, sin solver |
| `compose` | Ensambla lemas en una demostración, comprobando el empalme | Z3 | **proof**: cada lema, su certificado y el enlace |
| `synth` | CEGIS: ∃obj ∀entrada ∃aux | CEGIS/Z3 | objeto + contraejemplos que lo forzaron |
| `opt` | LP/ILP, o un packing | CBC | **dual exacto** = el certificado de cargas |
| `bounds` | Una desigualdad numérica, con rigor (`e`, `log`, `π`, `ζ`) | Arb o mpmath | **envolvente en racionales exactos** |
| `cases` | SAT con prueba DRAT verificada | CDCL propio o binario externo | prueba DRAT |
| `enum` | Grafos no isomorfos con filtros | nauty o Python | lista canónica + hash |
| `sweep` | Predicado y/o magnitud sobre una familia o CUALQUIER dominio finito | nauty o Python | familia **+ certificados del predicado** |
| `shrink` | Minimiza un contraejemplo (grafo o MUS) | CDCL / reducción | testigo de minimalidad |
| `bisect` | Umbral de una constante | prove o cases | el par que lo encierra |
| `verify` | Re-verifica un certificado guardado | — | — |
| `export` | Spec a SMT-LIB2/DIMACS, o un contraejemplo a Lean | — | — |
| `ledger` | Registro auditable de lo ejecutado | — | — |

Opciones comunes, **después** del subcomando: `--json`, `--cert FILE`,
`--timeout-ms`, `--rlimit`, `--max-memory-mb`, `--seed`.

Código de salida: `0` concluyente, `2` no concluyente, `1` certificado
inválido, `3` error.

## El DSL

Python como lenguaje anfitrión: un `.py` con una función `spec()`. Sin lenguaje
propio — un LLM escribe Python mucho mejor que SMT-LIB.

```python
import z3
from certo import Spec

def spec():
    a, b, c = z3.Reals("a b c")
    s = Spec()
    s.assume("a_pos", a > 0)      # hipótesis CON NOMBRE: core las usa
    s.assume("b_pos", b > 0)
    s.assume("c_pos", c > 0)
    s.claim((a+b)*(b+c)*(a+c) >= 8*a*b*c)
    return s
```

| Tipo | Comandos |
|---|---|
| `Spec` | `prove`, `check`, `core` |
| `SynthSpec` | `synth` |
| `LPSpec` | `opt` |
| `CNF` / `CNFSpec` | `cases`, `shrink` |
| `SweepSpec` | `sweep`, `shrink` |
| `DomainSpec` | `sweep` y `shrink` sobre cualquier dominio finito |
| `PackingSpec` | `opt` |
| `MultiSpec` | `core` multiobjetivo |
| `ProofSpec` | `compose` |
| `BoundSpec` | `bounds` |
| `BisectSpec` | `bisect` |

## Por qué el certificado es el centro

Con un LLM en el bucle el riesgo dominante no es la falta de ideas, es la
**plausibilidad sin verificación**. La regla de diseño es una sola:

> El LLM propone, el motor certifica, y el certificado sobrevive sin el LLM.

Los certificados marcados *sin solver* se comprueban con aritmética, evaluación
o propagación unitaria — no hay que confiar ni en Z3 ni en CBC:

| Tipo | Qué acredita | ¿Sin solver? |
|---|---|---|
| `lp_dual` | optimalidad exacta de un LP | **sí**, aritmética racional |
| `drat` | insatisfacibilidad de una CNF | **sí**, RUP/RAT |
| `cnf_model` | una asignación satisface la CNF | **sí**, evaluación |
| `farkas` | una combinación de las hipótesis que cierra el sistema | **sí**, sumando fracciones |
| `ball` | una cantidad real cae en un intervalo, y eso zanja la afirmación | **sí** para la afirmación; el intervalo necesita la spec |
| `proof` | los lemas **y** que cada uno se usa como su certificado permite | no, re-resuelve |
| `mus` | insatisfacibilidad **y** minimalidad | **sí** |
| `graph_set` | familia no isomorfa que pasa los filtros | **sí** |
| `sweep` | familia + certificados del predicado | según el predicado |
| `shrink_graph` | el contraejemplo es 1-minimal | sí (necesita el módulo de la spec) |
| `bisect` | el par que encierra el umbral | según sus hijos |
| `model` | contraejemplo de un `prove` | **sí**, sustituir y simplificar |
| `cegis` | el objeto no tiene contraejemplos | no, re-resuelve |
| `unsat_core` | las hipótesis son contradictorias | no, pero solo el núcleo |

Y detectan manipulación. Cambia a mano el objetivo de un dual y `verify` lo
caza; toca un paso de una prueba DRAT y deja de ser RUP.

### Procedencia

Cada certificado lleva la versión de `certo` que lo emitió y, si vino del CLI,
la ruta y el `sha256` de la spec. Si el fichero cambia después, `verify` avisa:
el certificado sigue siendo válido por sí mismo, pero ya no corresponde al
fichero que hay ahora.

## Qué establece de verdad un barrido

Un barrido que pasa y un barrido que pasa *con certificados* no son el mismo
resultado, y la distancia es grande. Así que el banner dice cuál te tocó:

| Nivel | Qué se sostiene | Cuándo |
|---|---|---|
| **certified** | cada evaluación lleva su certificado; no se confía en el predicado en absoluto | el predicado devuelve `Outcome(ok, cert=...)` **y** `--cert-all` los guarda |
| **reproducible** | el dominio, su hash y un vector de veredictos: reejecutar el predicado da las mismas respuestas | predicado `bool` pelado — el caso habitual |
| **recorded** | solo el dominio y su hash | la spec no está, se movió, o nunca se selló |

```
$ certo sweep spec.py
FINITE SWEEP REPRODUCIBLE -- the predicate is NOT certified  [unsat]
  the predicate holds on all 3481 items (FINITE DOMAIN, not the theorem)
  predicate_certified: 0
  predicate_uncertified: 3481
  !! 3481 de 3481 evaluaciones no llevan certificado. El barrido es
  REPRODUCIBLE --reejecutar el predicado da las mismas respuestas-- pero nada
  de esto establece que esas respuestas sean correctas.
```

Fíjate en las dos salvedades independientes. «No es el teorema» va de
**generalidad**: se comprobó un dominio finito, no todo `n`. «No certificado»
va de **confianza**: nada aquí dice que el predicado respondiera bien. Un
barrido que pasaba solo enunciaba la primera, y un banner verde sobre once mil
booleanos sin comprobar es donde eso más daño hace — no hay contraejemplo al
que ir a mirar.

### El replay: el nivel intermedio, con nombre

El certificado guarda un **vector de veredictos** —un carácter por elemento,
en orden de dominio— y su digest. `verify` reejecuta el predicado y compara:

```
$ certo verify out/sweep.json
VALID  domain_sweep certificate (reejecutando la spec, no confiando en sus respuestas)
  [ok] the family hash matches
  [ok] the item ids are unique
  [ok] re-running the predicate gives the same verdicts  (3481 evaluations, all identical)
  WARNING: 3481 de 3481 evaluaciones no llevan certificado. Reejecutarlas
  coincide, lo que hace el barrido reproducible; eso NO hace que las
  respuestas del predicado estén verificadas.
```

Es la única comprobación que pilla un predicado editado bajo un nombre
estable: el hash del dominio no puede —el dominio no se movió— y los
certificados guardados tampoco, porque no hay ninguno. Cuando discrepa, nombra
el elemento:

```
  [XX] re-running the predicate gives the same verdicts
       (item a=1,b=1 (index 0) now answers differently)
```

Dos consecuencias que conviene decir. Verificar cuesta ahora una reejecución
completa del predicado, que es el precio honesto de la afirmación. Y la
cabecera dice **«reejecutando la spec»** en vez de «sin solver»: el replay
ejecuta el Python de la spec, que bien puede llamar a un solver, así que la
redacción antigua era el mismo exceso un nivel más abajo.

### Cómo llegar a `certified`

Devuelve un `Outcome` con el certificado, y guárdalos todos:

```python
def predicate(item):
    res = lp.opt(build(item))
    return Outcome(ok=res.verdict is Verdict.PROVED, cert=res.certificate)
```

```bash
certo sweep spec.py --cert-all
```

Hacen falta las dos mitades. Un predicado que certifica cada respuesta pero
corre con `--cert-all` apagado solo conserva los certificados de los
contraejemplos, así que el certificado lleva uno de veintiuno — y lo dice.
**Un certificado solo puede atestiguar lo que de verdad contiene.**

## Las demostraciones vacuas se detectan, no se celebran

`prove` tiene éxito cuando `hipótesis ∧ ¬objetivo` es insatisfacible. Si las
hipótesis ya son insatisfacibles *por sí solas*, eso ocurre para **cualquier**
objetivo. La demostración es válida —de una contradicción se sigue todo— y no
dice absolutamente nada.

Es la forma más embarazosa de equivocarse y la más fácil de pasar por alto,
porque la salida es idéntica a la de un éxito. Así que se comprueba en cada
`prove`, `core`, `farkas` y `compose` que sale bien:

```
$ certo prove vacua.py --lang es
DEMOSTRADO -- simbólico y universal bajo las hipótesis  [unsat]
  VACUA: las hipótesis se contradicen entre sí, así que este objetivo --y
  cualquier otro-- se sigue. La demostración es válida y no dice nada. Corre
  `check` solo sobre las hipótesis para ver qué par choca.
  !! las hipótesis son contradictorias: esta demostración es vacua
```

El veredicto no cambia, porque el veredicto no está mal. Lo que cambia es que
te lo dicen. Y se sigue diciendo: la marca viaja en el certificado, así que
`verify` lo repite meses después, cuando la ejecución ya se olvidó y solo
queda el artefacto.

```
$ certo verify out/vacua.json
VALID  unsat_core certificate (verified with a solver)
  [ok] the core is unsatisfiable  (unsat)
  WARNING: VACUOUS: this core does not include the negated goal, so the
  hypotheses contradict each other and the proof holds for any goal.
```

Dos detalles que conviene saber:

* **Cuesta una llamada extra al solver, solo en el camino de éxito**, y esa
  llamada es sobre un problema estrictamente más fácil que el que se acaba de
  resolver: las hipótesis sin el objetivo.
* **En `farkas` no se puede leer de los multiplicadores.** Un multiplicador
  cero sobre el objetivo negado sugeriría vacuidad, pero el LP es libre de
  darle peso no nulo a esa fila aunque no la necesite, y suele hacerlo. Así
  que la pregunta se hace directamente: se quita la fila del objetivo (y, en
  modo `--nonlinear`, toda fila derivada de ella) y se busca otra vez.

En `compose` la comprobación cae donde más importa. Dos lemas *derivados* no
pueden contradecirse nunca: los dos son ciertos. Solo pueden los **puentes**,
porque un puente se aserta en vez de derivarse. Dos puentes que chocan hacen
vacuo el teorema entero, y eso se informa con nombre y apellido.

## `bounds`: números, con rigor

`prove` y `farkas` son exactos, pero algebraicos. En cuanto una demostración
dice «esta constante está por debajo de 0.4» y la constante lleva `e`, `log`,
`π` o `ζ`, ninguno de los dos la ve siquiera — y «lo calculé y da 0.397» no es
una afirmación sobre nada. Un float no dice nada del valor verdadero.

Una envolvente sí. Cada operación devuelve un intervalo que contiene
demostrablemente el valor verdadero, así que una desigualdad que se cumple
para todo el intervalo se cumple para el número.

```python
from certo import BoundSpec

def spec():
    return BoundSpec(
        value=lambda m: m.e / m.pi,     # m = constantes y funciones rigurosas
        claim=("<", "0.866"),           # contra un racional EXACTO, como cadena
        describe="e / pi",
        prec=64,
    )
```

```
$ certo bounds examples/bounds_constant.py --cert out/epi.json --lang es
DEMOSTRADO  [unsat]
  el valor es < 0.866 -- establecido rigurosamente con 64 bits
  backend: python-flint (Arb)
  envolvente: [0.8652559794322651, 0.8652559794322651]  anchura 3.062e-19
  precisiones probadas: 64 bits
```

### La precisión es el presupuesto de trabajo

Igual que `rlimit` para Z3. La búsqueda empieza en `prec` bits y los dobla
hasta que la envolvente zanja la afirmación. La aritmética de bolas pierde
precisión en las cancelaciones, así que **cuánta precisión necesita una
expresión es una propiedad de la expresión, no de la respuesta** — adivinarla
una vez e imprimir lo que salga es como se acaba citando un número que no se
ha establecido.

Y cuando se agota, lo dice como la tercera respuesta, no como una refutación:

```
$ certo bounds cancelacion.py --lang es    # el valor es exp(1) - e, o sea cero
INCONCLUYENTE  [resource_exhausted]
  la envolvente [-5.99e-154, 5.99e-154] sigue a caballo de la cota con 512
  bits. Esto no es una refutación: sube max_prec, o reescribe la expresión
  donde se cancela
```

Esa es la respuesta honesta, y es una que un resultado en coma flotante no
puede dar nunca. Ninguna envolvente demostrará jamás que una cantidad es no
nula cuando de hecho es cero.

### Qué lleva el certificado

La envolvente viaja en **racionales exactos**, así que la verificación se parte
en dos y las mitades fallan distinto:

```
$ certo verify out/epi.json
VALID  ball certificate (verified without a solver)
  [ok] the enclosure is an interval       ([0.8652559794322651, 0.865255979432265])
  [ok] the enclosure settles the claim    (the value is < 0.866)
  [ok] re-evaluating the spec lands inside it
  64 bits via python-flint (Arb)
```

Si el intervalo zanja la afirmación se decide comparando fracciones, sin
ninguna biblioteca de por medio. Si es el intervalo *correcto* necesita la
spec y el mismo backend — y cuando eso no se puede rehacer, se informa como no
comprobado en vez de darlo por bueno en silencio.

### Los floats se rechazan

`0.1` no es un décimo. Es `3602879701896397/2^55`, y una envolvente construida
a partir de ahí sería perfectamente rigurosa sobre el número equivocado. Así
que un float de Python en cualquier parte de la expresión levanta un error,
con esa explicación:

```python
value=lambda m: m.pi * 0.5      # rechazado
value=lambda m: m.pi * m("1/2") # bien, y exacto
```

Es la única forma en que la garantía podría perderse en silencio, así que es lo
único que detiene la ejecución.

### Backends

| Backend | Cubre | Notas |
|---|---|---|
| `python-flint` (Arb) | todo lo de abajo, más `gamma`, `lgamma`, `digamma`, `zeta`, `erf`, `erfc`, las inversas y las hiperbólicas | preferido; `pip install python-flint` |
| `mpmath.iv` | `exp`, `log`, `sqrt`, `sin`, `cos`, `tan`, `gamma` | Python puro, casi siempre ya instalado |

El backend queda registrado en el certificado, porque una cota vale lo que
valga lo que la produjo. Pedirle `zeta` a `mpmath.iv` lo dice en vez de caer en
una evaluación no rigurosa.

Deja `claim` fuera para **medir** en vez de decidir: el certificado registra
entonces la envolvente alcanzada, igual que `sweep --collect` mide sin refutar.

## `compose`: de una carpeta de certificados a una demostración

Todos los demás comandos producen una hoja. Una demostración es «Lema A y
Lema B, luego el teorema», y ese empalme es la parte que nadie comprueba. Un
lema demostrado bajo una hipótesis y usado bajo otra ligeramente distinta es
la forma clásica en que se rompe un argumento ensamblado, y es completamente
invisible cuando los certificados están uno al lado del otro en un directorio.

```python
from certo import ProofSpec, Spec

def spec():
    p = ProofSpec(title="R(3,3) = 6")
    p.assume("n_ge_6", n >= 6)                  # hipótesis del TEOREMA

    p.lemma("upper", certificate="out/r33_k6.json",
            states=(R33 <= 6),
            bridge="la prueba DRAT cierra la codificación de K6; leer eso "
                   "como R(3,3) <= 6 es lo que la codificación significa")

    p.lemma("lower", certificate="out/r33_k5.json",
            states=(R33 > 5),
            bridge="el modelo es una 2-coloración de K5 sin triángulo "
                   "monocromático, luego R(3,3) > 5")

    p.lemma("spare", proves=alguna_spec)        # se demuestra ahora, con `prove`
    p.conclude(z3.And(R33 == 6, n >= R33))
    return p
```

```
$ certo compose examples/compose_proof.py
PROVED  [unsat]
  theorem assembled from 3 lemmas (1 derived and linked, 2 asserted)
  lemmas:
    upper                    BRIDGE     *
    lower                    BRIDGE     *
    spare                    linked
  NOT needed: spare
```

### Qué se comprueba de verdad

Un lema dado con `proves=` queda **demostrado y enlazado**. Enlazado
significa: lo que el certificado de ese lema cierra realmente *implica* el
enunciado que se le pasa al paso final. La comprobación es uniforme, porque
todo certificado que valga la pena componer responde a la misma pregunta
—«¿qué fórmulas demostraste conjuntamente insatisfacibles?»— y el enlace es

```
not(enunciado)  =>  esas fórmulas
```

lo que, junto con la verificación del propio certificado (esas fórmulas son
contradictorias), da exactamente: el enunciado es válido. **Si el enlace
falla, no se emite nada.** Un lema demostrado para `x >= 1` y declarado como
`x >= 2` se rechaza con su nombre, en el momento de ensamblar.

### Puentes: la parte honesta

Un lema dado con `certificate=` es un **puente**. Una prueba DRAT habla de
variables proposicionales llamadas `e0_1`; no habla de un número de Ramsey. El
paso de «esta codificación es insatisfacible» a «R(3,3) ≤ 6» es el
*significado* de la codificación, y ningún verificador puede confirmarlo.

Así que los puentes no se rechazan: se hacen visibles. El certificado se
verifica por su cuenta, el paso se declara en prosa, y se informa con su
nombre **cada vez que se verifica la demostración**:

```
$ certo verify out/proof.json
VALID  proof certificate (verified with a solver)
  [ok] lemma upper holds  (drat: 23 steps (23 RUP, 0 RAT, 0 deletions))
  [ok] lemma lower holds  (cnf_model)
  [ok] lemma spare: its certificate entails the statement used  (2 obligations)
  [ok] the final step holds
  [ok] the final step uses only the lemmas and the theorem's own hypotheses
  [ok] nothing entered the proof undeclared
  WARNING: BRIDGE: upper is asserted, not derived -- ...
  WARNING: BRIDGE: lower is asserted, not derived -- ...
  WARNING: lemmas the theorem does not need: spare
```

El puente está en la cabeza de quien escribe en cualquier caso. La diferencia
es si quien lee lo puede ver y sopesar.

### El «NO hacen falta» sale de la demostración, no de una conjetura

El paso final es un `prove` corriente, así que su núcleo insatisfacible dice
qué lemas usó el teorema de verdad. Esperable que pille más de lo que parece:
sobre aritmética lineal real Z3 rederiva por su cuenta la mayoría de los lemas
auxiliares, y los que sobreviven como *necesarios* son justo los que aportan
algo que la teoría no alcanza sola — que suele ser un puente.

## `farkas`: `linarith` y `nlinarith`, con el certificado incluido

El `linarith` de Lean cierra un objetivo y no cuenta cómo. `certo farkas` hace
la misma búsqueda y devuelve la razón: los **multiplicadores racionales no
negativos** que combinan las hipótesis con el objetivo negado hasta que todo
se cancela y lo que queda es falso.

```python
# examples/farkas_linear.py
import z3
from certo import Spec

def spec():
    x, y, z = z3.Reals("x y z")
    s = Spec()
    s.assume("x_ge_1", x >= 1)
    s.assume("y_ge_1", y >= 1)
    s.assume("noise",  z <= 100)      # cierta, e irrelevante
    s.claim(x + y >= 2)
    return s
```

```
$ certo farkas examples/farkas_linear.py
PROVED  [unsat]
  Farkas (linarith) certificate found: 3 hypotheses with a non-zero multiplier
  multipliers:
    x_ge_1                 1
    y_ge_1                 1
    __goal__               1
  Lean: linarith [x_ge_1, y_ge_1]
```

Tres cosas que mirar. `noise` no aparece, porque su multiplicador es 0 -- **el
certificado dice qué hipótesis usa la demostración de verdad**, que es `core`
gratis y justo lo que hace falta para que una interfaz hacia Lean quede
pequeña. Los multiplicadores son racionales exactos, así que el resultado es
una demostración que un árbitro rehace en papel: `1*(x-1) + 1*(y-1) +
1*(2-x-y) = 0`, y el objetivo negado era estricto, luego `0 < 0`. Y la línea
`Lean:` es la llamada al táctico lista para pegar, con la lista de hipótesis
ya recortada.

### `--nonlinear` es `nlinarith`

`nlinarith` no es otro algoritmo. Multiplica pares de hipótesis, añade algunos
cuadrados, trata cada monomio como una variable nueva y corre la búsqueda
lineal sobre eso. `--nonlinear` hace lo mismo, fielmente, heurística incluida:

```
$ certo farkas examples/farkas_nonlinear.py --nonlinear
PROVED  [unsat]
  degree-2 Positivstellensatz (nlinarith) certificate found: 2 hypotheses
  multipliers:
    __goal__               1
    sq_a_b                 1
  Lean: nlinarith
```

El objetivo era `a^2 + b^2 >= 2ab` y `sq_a_b` es la fila `(a-b)^2 >= 0`. Esa
es la demostración humana de esa desigualdad, redescubierta -- y con nombre,
así que la redacción se escribe sola.

### La verificación no usa solver

```
$ certo verify out/farkas.json
VALID  farkas certificate (verified without a solver)
  [ok] every multiplier is non-negative  (2 of 5 non-zero)
  [ok] the combination cancels every monomial  (left over: )
  [ok] the remaining constant is a contradiction  (0 < 0 is false)
  [ok] the declared constant and strictness match  (0)
  WARNING: 4 rows are products or squares derived from the hypotheses
  5 rows combined; pure exact arithmetic
```

El certificado lleva las filas, así que comprobarlo es sumar fracciones. Sin
Z3, sin LP, sin nada en que confiar. El aviso es deliberado: en modo
`--nonlinear` algunas filas son *derivadas*, y quien lee debe saber cuáles.

### Cuando no encuentra nada

`farkas` es **incompleto a propósito**, en los dos modos -- Farkas es completo
para la aritmética lineal real, pero solo una vez que están presentes las
filas adecuadas, y en modo `--nonlinear` qué productos añadir es una
conjetura. Así que «sin certificado» nunca significa «falso»; significa que
esta búsqueda no lo cerró. `prove` usa el `nlsat` de Z3, que *sí* es completo
para la aritmética real. El reparto:

> **`prove` para saber. `farkas` para certificar.**

Una ejecución lineal sobre un objetivo no lineal lo dice y apunta a
`--nonlinear` en vez de informar de un fallo.

<details>
<summary>¿Por qué no un certificado SOS de verdad con un SDP?</summary>

Porque un SDP se resuelve en coma flotante, así que lo que vuelve no es
exacto, y un certificado inexacto no es citable -- la misma razón por la que
`opt` reconstruye racionales en vez de imprimir los flotantes del solver. Una
heurística de grado 2 cuya salida es exacta vale más que una de grado *d* cuya
salida necesita una nota al pie.
</details>

## Modo exacto en `opt`

CBC trabaja en punto flotante: devuelve `10.66666656003499` donde la respuesta
es `32/3`. Con eso no se puede afirmar igualdad primal-dual ni citar una
constante.

`certo` resuelve en flotante, **reconstruye racionales y verifica en
`Fraction`**, aceptando solo si la comprobación exacta pasa — así una
reconstrucción mala se rechaza sola:

```
$ certo opt examples/lp_mixed_packing.py
  optimo EXACTO certificado: 25/2 (denominador <= 6)
  min_dual: 5/6

$ certo verify out/lp.json
VALIDO  certificado lp_dual (verificado sin solver)
  [ok] primal no negativo (x >= 0)
  [ok] factibilidad primal (A x <= b)
  [ok] dual no negativo (y >= 0)  (min(y)=5/6)
  [ok] factibilidad dual (A^T y >= c)
  [ok] dualidad fuerte exacta (c.x == b.y)  (c.x=25/2 | b.y=25/2)
  aritmetica racional EXACTA, sin tolerancias
```

Los coeficientes admiten `int`, `Fraction`, la cadena `"7/12"` o `float`:

```python
lp.objective({"x": Fraction(7, 12), "y": "1/3"})
lp.constraint({"x": 1, "y": 1}, "<=", Fraction(1, 2), name="cap")
```

`--no-exact` salta la reconstrucción; el certificado queda en flotante y
`verify` lo marca como **no citable**.

## Barridos citables

Un predicado que devuelve `True`/`False` deja el barrido a medias: el
certificado acredita **qué familia** se examinó, pero no que el predicado se
evaluara bien en cada grafo. Si dentro hay un LP en punto flotante, esa es
justo la parte que un árbitro querría comprobar.

Devuelve `Outcome` y el barrido pasa a ser citable:

```python
from certo import Outcome

def pred(g):
    res = lp.opt(packing_lp(g))
    return Outcome(ok=..., cert=res.certificate,
                   detail="W* = " + res.meta["objective"])
```

`verify` los comprueba en cascada; si faltan, avisa. Ver
[`examples/sweep_certified_lp.py`](examples/sweep_certified_lp.py).

`ok=None` significa «no concluyó». Un predicado que revienta o no concluye ya no
tumba el barrido entero, pero impide afirmar que se cumple en toda la familia.
Un contraejemplo, en cambio, refuta aunque otros grafos fallaran.

## Calibrar, no solo refutar

Muchas veces la pregunta no es «¿falla?» sino «¿**cuánto** falla, y dónde es
peor?». Para eso `SweepSpec` acepta `collect`:

```python
SweepSpec(n=5, filters=["connected"], collect=lambda g: razon(g), worst="min")
```

```
$ certo sweep spec.py --worst 3
CALIBRACION sobre 21 grafos: min=2/5 (D?{)  max=1 (D~{)  media=13/21
  3 menores: D?{ 2/5 | DCw 2/5 | DEg 2/5
```

Si devuelves `Fraction`, la estadística sigue siendo **exacta**: `2/5`, no
`0.4`. El certificado guarda los valores y `verify` recomputa min, max y media
para comprobar que cuadran. `predicate` es opcional — se puede medir sin
refutar nada — y también vale devolver `Outcome(..., value=...)` desde el
predicado para no calcular dos veces.

## De candidato acotado a teorema

`synth` busca en un dominio **acotado**: encuentra un candidato, no demuestra
nada sobre el resto. Pasar de ahí al enunciado general era un paso manual, que
es donde se cuelan los errores. `--prove-candidate` lo encadena:

```
$ certo synth examples/synth_prove_identity.py --prove-candidate
CANDIDATO SINTETIZADO -- sintesis ACOTADA  [sat]
  objeto sintetizado:
    A = 2
    B = -2
  dominio: And(x >= 1, x <= 20)

PRUEBA SIMBOLICA UNIVERSAL: PASS  [unsat]
```

El certificado combinado lleva las dos mitades y `verify` comprueba cada una
por separado — porque dicen cosas distintas: la primera es un **descubrimiento
acotado**, la segunda un **teorema**.

La spec tiene que declarar cuál es el enunciado general, porque no es
deducible: normalmente cambia el dominio **y el sort**. Se busca sobre enteros
acotados y se demuestra sobre los reales, que es donde la aritmética
polinómica sí es decidible.

```python
SynthSpec(
    ...,
    behavior=z3.And(x >= 1, x <= 20),          # dominio acotado de búsqueda
    universal=lambda vals: Spec().claim(...),  # enunciado general
    # o, caso simple:  universal_behavior=<expr que sustituye a behavior>
)
```

## Más allá de los grafos

Los grafos son un dominio entre otros. `DomainSpec` corre el mismo patrón
exhaustivo —mismos seis estados, mismos certificados del predicado, misma
calibración— sobre cualquier cosa enumerable:

```python
from certo import DomainSpec

def spec():
    return DomainSpec(
        items=[(s, r) for s in range(2, 8) for r in range(2, 8)],
        predicate=lambda p: se_cumple(*p),
        collect=lambda p: razon(*p),
        key=lambda p: "s={},r={}".format(*p),
    )
```

`key` convierte un elemento en un id estable: es lo que va al certificado, así
que tiene que identificarlo sin ambigüedad. `verify` comprueba que los ids son
únicos; lo que no puede comprobar es que el dominio esté COMPLETO — eso lo
define la spec.

### Filtros programables

`filters` acepta callables además de los nombrados, así que una familia que el
catálogo no conoce se cuenta igual de bien:

```python
SweepSpec(n=6, filters=["connected", es_split], predicate=...)
```

Los recuentos quedan separados (`enumerated` antes de filtrar, `in_family`
después), y `verify` dice sin rodeos que un filtro programable no se puede
recomprobar desde el certificado, porque vive en la spec.

### ¿A partir de qué n falla?

```bash
certo sweep spec.py --n-range 3..8 --stop-on-first
```

Un subcertificado por tamaño, cada uno verificado por separado. Lo que añade
el rango es el ORDEN y la afirmación de que nada falló por debajo del primer
fallo. Con `--stop-on-first` los tamaños mayores no se ejecutaron, y el
certificado lo registra. Disponible también por MCP (`n_range="3..8"`).

### Minimizar sobre un dominio cualquiera

`shrink` también acepta `DomainSpec`, pero necesita saber qué significa «un
paso más pequeño». No hay default sensato, así que se declara:

```python
DomainSpec(..., reduce=lambda p: [(p[0] - 1, p[1]), (p[0], p[1] - 1)])
```

La traza guarda el ÍNDICE tomado en `reduce()` en cada paso, no solo el id
resultante. Eso permite que la verificación repita el descenso exacto en vez
de rehacer la búsqueda.

## Packings

Clicos compitiendo por aristas, bloques compitiendo por puntos: la forma se
repite, y rehacer el LP a mano cada vez es donde se esconden los errores.

```python
from certo import PackingSpec
from certo.graphs import Graph

def spec():
    g = Graph.from_edges(6, [...])
    return PackingSpec.cliques_in_graph(g, gains={3: 2, 4: 5})
```

`to_lp()` devuelve un `LPSpec`, así que los racionales exactos y el dual
verificable vienen gratis. **El dual es el certificado de cargas**: los
nombres de restricción son nombres de recurso, así que `y_r` se lee como «la
carga del recurso r» — que suele ser el objeto que de verdad querías.

```
$ certo opt examples/packing_mixed.py --by-type
  mixed      25/2       EXACT optimum certified: 25/2
  K3         10         EXACT optimum certified: 10
  K4         25/2       EXACT optimum certified: 25/2
```

Si mezclar aporta algo es exactamente el hueco entre el óptimo mixto y el
mejor tipo suelto. Aquí, sobre K6, no aporta nada sobre K4 puro.

## `core` sobre varios objetivos

Correr `core` una vez por objetivo ya dice qué hipótesis necesita cada uno. Lo
que añade la tabla es la COMPARACIÓN, y eso es lo que decide cuán pequeña
puede ser una interfaz hacia Lean.

```
$ certo core examples/core_matrix.py
  hypothesis  identity  positivi  ordering
  r_ge_3            no       yes        no
  d_ge_1            no        no        no
  d_le_r            no        no       yes
  never used by any goal: d_ge_1
```

Una hipótesis irrelevante para la identidad pero necesaria para la
positividad es invisible cuando los objetivos se miran de uno en uno. El
certificado lleva un núcleo por objetivo y `verify` comprueba, además, que
**la tabla dice exactamente lo que dicen los núcleos**.

## Registro auditable

Seis meses después, «eso lo comprobamos» no vale nada sin el artefacto.

```bash
certo opt spec.py --cert c.json --log --note "cota K6" --tag paper
certo ledger verify
```

```
  [ok] 2026-09-16T00:45:23  core     core of 4 formulas
  [!!] 2026-09-16T00:45:25  opt      digest 3653579e... != logged 681631ea...
  2 entradas: 1 verificadas, 0 FALLAN, 1 cambiadas desde que se registraron
```

Dos propiedades deliberadas: es **solo-añadir** —una ejecución posterior que
contradiga a otra es una línea nueva, no una edición— y **no copia
certificados**, guarda su ruta y su digest. `ledger verify` los relee y los
re-verifica, así que un certificado manipulado o ausente sale como fallo en
vez de quedar duplicado en el log.

## Export a Lean

```bash
certo export out/shrink.json --lean --out Contraejemplo.lean
```

Emite el contraejemplo como **datos** Lean 4 más un esqueleto. La separación
es deliberada y la cabecera del fichero lo dice:

**Compila**: comprobado contra Lean v4.28.0 con su Mathlib, incluidas las dos
comprobaciones `example`, que son demostraciones de verdad por `decide`. Otra
versión puede necesitar ajustes; la lista de aristas es exacta en cualquier
caso.

Llegar ahí costó tres rondas contra un compilador real —`loopless` no se podía
`decide`, y `edgeFinset` no está en `SimpleGraph.Basic`—, que es justo la razón
por la que emitir Lean sin compilarlo es mala idea. Usa `SimpleGraph.fromRel`,
que simetriza y quita bucles por su cuenta, así que no quedan obligaciones que
se rompan cuando Mathlib mueve `Irreflexive` de sitio.

Existe porque transcribir un contraejemplo a Lean a mano es mecánico, y lo
mecánico es justo donde se cuelan los errores.

## El alcance sale en pantalla

Un `DEMOSTRADO` a secas invita a leer una síntesis acotada como un teorema.
Cada comando dice de qué alcance habla:

```
$ certo synth examples/synth_constant.py
CANDIDATO SINTETIZADO -- sintesis ACOTADA  [sat]
  objeto sintetizado:
    a = 10
    b = 0
  dominio: And(x >= 1, x <= 20)
  ESTO NO ES UNA PRUEBA UNIVERSAL: el candidato vale en el dominio de
  arriba y nada mas. Para el enunciado general, escribe un Spec
  simbolico con estos valores fijados y pasalo por `certo prove`.
```

## Servidor MCP

Todos los comandos expuestos al LLM, sin copiar y pegar. El proyecto trae un
[`.mcp.json`](.mcp.json) listo; para registrarlo a mano en Claude Code:

```bash
claude mcp add certo --env CERTO_WORKSPACE=. -- certo-mcp
```

`CERTO_WORKSPACE` (por defecto el directorio actual) contiene `specs/` y
`certs/`. **Todas las rutas se confinan ahí.**

Tres decisiones de diseño:

1. **Los certificados no vuelven en la respuesta.** Un MUS ocupa 18× más en
   disco que toda la respuesta, y el modelo no puede verificarlo leyéndolo. Se
   escriben a disco y vuelve la ruta, el tipo y el digest.
2. **Los errores vuelven como dato, no como excepción.** El SDK convierte
   cualquier excepción en `Error executing tool X` y se come el motivo; un
   modelo que lee eso no puede arreglar su spec. Aquí recibe qué pasó y con qué
   corregirlo.
3. **`dsl_guide` primero.** Va como herramienta y como recurso (`certo://dsl`).

> **Las specs son código Python y se ejecutan al cargarlas.** Es inherente al
> DSL y es el mismo nivel de confianza que ya tiene un agente con acceso a
> ficheros. El servidor confina rutas, pero **no es un sandbox**: no lo expongas
> a specs de terceros.

## Qué no hace

Esta sección importa tanto como la de los doce comandos.

**El límite duro son los enunciados asintóticos con cuantificadores sobre `n`.**
«Existe `N` tal que para todo `n ≥ N`, todo grafo…, la pérdida es `≤ εn²`» no se
decide con esta herramienta. `prove` y `synth` trabajan sobre fórmulas
decidibles o dominios acotados; `sweep` y `cases` sobre familias finitas.

La escalera, con los números de Ramsey como ejemplo:

| Pregunta | ¿`certo`? |
|---|---|
| ¿R(3,3) ≤ 6? | **Sí.** `cases`, prueba DRAT de 23 líneas, verificada |
| ¿R(3,3) = 6? | **Sí.** `bisect`, umbral certificado por los dos lados |
| ¿R(5,5) ≤ 48? | **No en la práctica.** Finito, pero el espacio es 2^903 |
| ¿Converge R(k,k)^(1/k)? | **No, en principio.** Asintótico: no es expresable |

Más límites, dichos también en cada salida:

- `sweep` y `cases` demuestran el **caso finito**, no el teorema.
- El certificado `graph_set` verifica no isomorfía y filtros, **no completitud**.
- En ILP el dual certifica la **cota de la relajación**, no la optimalidad entera.
- `shrink` da un contraejemplo **1-minimal, no mínimo**.
- `bisect` **supone monotonía** en el parámetro; comprueba los extremos y avisa
  si no cuadran, pero la monotonía no se demuestra.
- La eliminación de cuantificadores sobre los reales es doblemente exponencial y
  se cuelga en ejemplos de libro; por eso `qe` no está entre los comandos.

**El nicho es claro:** descubrir objetos, destruir formulaciones falsas y
minimizar hipótesis antes de pagar el coste de formalizarlas.

## FAQ

**¿Es un demostrador de teoremas?**
No. Decide fórmulas en teorías decidibles y verifica casos finitos. Para el
teorema, Lean o Rocq. `certo` es la capa de antes.

**Si ya confío en Z3, ¿para qué el certificado?**
Para que no tenga que confiar quien lea tu paper. Un `unsat` de Z3 es una
afirmación; una prueba DRAT verificada es algo que un árbitro comprueba en su
máquina sin ejecutar tu código. Y sirve de red: si el solver tuviera un fallo,
el certificado no verifica y sale `ERROR`, no `DEMOSTRADO`.

**¿Qué significa `unknown_solver`? ¿Es «no existe»?**
No. Significa que el solver terminó sin concluir. `timeout` es que se acabó el
reloj, `resource_exhausted` que se acabó el presupuesto, `out_of_theory` que la
fórmula se sale del fragmento decidible. Los cuatro son distintos de `unsat`,
que sí es «no existe».

**¿Por qué mi `opt` salió en flotante?**
Porque la reconstrucción racional no encontró un denominador que verificara
exactamente. El resultado sigue siendo útil para explorar, pero `verify` lo
marca como no citable. Suele pasar cuando los datos de entrada ya eran
flotantes: pásalos como `Fraction` o como cadena `"7/12"`.

**¿Por qué el solver SAT propio es lento?**
Porque es un CDCL en Python. Existe porque el *proof logging* de pysat no
funciona en Windows —devuelve 0 líneas con todos sus solvers— y sin prueba no
hay certificado. Para instancias grandes:
`certo cases spec.py --solver-binary /ruta/a/cadical`.

**¿Puedo fiarme de ese CDCL?**
No hace falta. Si emitiera una prueba mal formada, el verificador DRUP la
rechaza y sale `ERROR`. Hay además un test diferencial contra Z3 sobre CNF
aleatorias. **El verificador audita al solver.**

**¿Los resultados son reproducibles?**
Los de los motores propios sí: el presupuesto es de trabajo, no de tiempo. Tu
predicado de `sweep` queda fuera de esa garantía.

**¿Qué pasa si cambio la spec después de generar un certificado?**
`verify` lo sigue dando por válido —se verifica solo— pero avisa de que ya no
corresponde al fichero actual.

**¿`synth` demuestra algo?**
Encuentra un candidato en el dominio acotado que declaraste. Eso es un
descubrimiento, no un teorema — y la salida lo dice en el banner. Para el
enunciado general, `--prove-candidate`.

**¿Cómo conecto esto con Lean?**
Hoy, a mano: `certo` te da el contraejemplo, el valor sintetizado o las
hipótesis que de verdad hacen falta, y tú escribes el enunciado. La exportación
automática de contraejemplos a definiciones Lean está en la lista.

**¿Puedo usarlo sin conexión y sin instalar nada más?**
Sí. `z3-solver` y `pulp` traen sus binarios; el resto es Python puro.

## Tests

131, y sin necesidad de ningún framework de tests.

```bash
for t in smoke mcp i18n extras; do python tests/test_$t.py; done
```

En [BACKLOG.md](BACKLOG.md) está lo que viene y lo que deliberadamente no.

## Licencia

MIT. El motor de síntesis es una reimplementación del algoritmo CEGIS de
[marcelwa/CEGIS](https://github.com/marcelwa/CEGIS) (MIT), no de su código.

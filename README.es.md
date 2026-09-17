# certo

**Entre tener una idea matemática y tener una demostración de ella hay mucho
trabajo que no es demostrar.** certo hace ese trabajo —encontrar el objeto,
romper las afirmaciones falsas, medir lo que sobrevive, reducirlo a lo que
realmente es, y ensamblar el resto— y cada paso vuelve con un **certificado
que cualquiera puede re-comprobar sin fiarse de certo.**

CLI y MCP. Veintisiete comandos. Corre en milisegundos donde una
formalización cuesta horas.

*English: [README.md](README.md) · cualquier comando acepta `--lang en`.*

---

## El arco

| Fase | Qué preguntas | Qué vuelve |
|---|---|---|
| **Encontrar** | ¿Existe un objeto así? ¿Cuál es el mejor? | el objeto —y con `mixed --prove-optimal`, una demostración de que *es* el mejor |
| **Romper** | ¿Es cierta esta afirmación? | un contraejemplo **con valores concretos**, en milisegundos |
| **Medir** | No *si* falla: **cuánto**, y ¿dónde es peor? | mínimo, máximo y media exactos, y las instancias extremas por nombre |
| **Reducir** | Noventa contraejemplos. ¿Cuántos objetos son en realidad? | órbitas bajo tu simetría, y un testigo minimal por órbita |
| **Establecer** | ¿Vale para todos los casos, para todo `n`, exactamente? | pruebas DRAT, inducción con la cadena comprobada, multiplicadores de Farkas, cofactores de Gröbner, sumas de cuadrados, encierros rigurosos |
| **Ensamblar** | ¿Sobre qué descansa todo mi proyecto, y qué sigo debiendo? | la demostración con cada **puente nombrado**, y un informe de lo que sigue supuesto |

El hilo conductor es la última columna. Un veredicto que no puedes
re-comprobar es un rumor; todo aquí produce un artefacto, y la mayoría se
comprueban sin solver alguno.

---

### Encuentra el objeto — y demuestra que es el mejor

```
$ certo mixed examples/walkthrough.py --prove-optimal
DEMOSTRADO  [unsat]
  ÓPTIMO 7, DEMOSTRADO: 73 nodos, 37 de ellos cerrados con certificado
  73 nodos: 19 cerrados por cota, 18 infactibles, 0 totalmente fijados
```

No «el solver dijo 7». Branch and bound donde **cada hoja lleva su propio
certificado** —un dual exacto, un rayo de Farkas, o un LP residual totalmente
fijado— y se comprueba que el árbol cubre el dominio entero. `certo synth`
hace el mismo trabajo por CEGIS cuando el objeto es una fórmula y no un
diseño, y dice sin rodeos que su búsqueda fue acotada.

### Rompe las que son falsas, y te enseña qué las rompió

```
$ certo prove examples/refute_density.py
REFUTADO  [sat]
  el contraejemplo:
    dens = 7/8
    kappa = 4
  certificado: model (sin solver, id 1a76b821f2cafa42)
  motor: z3:5.1.0 | 4.2 ms
```

**Cuatro milisegundos**, y la respuesta no es «no» —es `dens = 7/8`, que pasa
todas las hipótesis y no está ni cerca del «casi completo» que la afirmación
suponía—. Ese número te dice por dónde arreglar el enunciado.

### Mide cuánto, no solo si

```
$ certo sweep examples/calibrate_density.py
SATISFACIBLE  [sat]
  CALIBRACIÓN sobre 156 grafos: mín=0 (E???)  máx=1 (E~~w)  media=1/2
```

Racionales exactos, y los extremos nombrados. Que una conjetura falle es un
dato; *cuánto falla y sobre qué objeto* es lo que te dice si debilitarla o
abandonarla.

### Convierte noventa fallos en los dos objetos que son

```
$ certo sweep examples/setfamily_sweep.py --witnesses
REFUTADO  [sat]
  REFUTADO: 90 contraejemplos de 120 examinados -- 90 etiquetados, 2 salvo simetría
  orbit_count: 2
```

Noventa contraejemplos no son noventa problemas. Declaras la simetría y certo
cuocienta por ella, se queda con un testigo **minimal** por órbita, y
certifica que la descomposición cuadra.

### Y te dice cuándo una demostración no iba de nada

```
$ certo prove examples/lint_vacuous_regime.py
DEMOSTRADO -- simbólico y universal bajo las hipótesis  [unsat]
  VACUA: estas hipótesis se contradicen entre sí, así que este objetivo --y
  cualquier otro-- se sigue. La demostración es válida y no dice nada.
  El choque es: kappa_large, density_high, sparse
```

Lean demostrará ese teorema, no reportará ningún `sorry`, y `#print axioms`
saldrá limpio. Nada de eso te dice que las hipótesis fueran satisfacibles. Un
usuario tenía **cuatro** módulos Lean así.

### Y cada una deja algo que puedes re-comprobar después

```
$ certo verify out/optimal.json
VÁLIDO  certificado branch_bound (verificado con solver)
  [ok] ningún nodo aparece dos veces  (0 duplicados)
  [ok] el diseño incumbente existe y alcanza el óptimo  (declarado 7)
  [ok] toda rama tiene todos sus hijos  (faltan 0: -)
  [ok] todo nodo hoja está cerrado con un certificado  (0 sin cerrar: -)
```

Meses después, solo con el artefacto, y con los avisos repetidos —una
demostración vacua sigue diciendo que es vacua, un barrido sigue diciendo qué
no certificó—. `certo status` hace esto con un directorio entero, y te dice
qué sigue debiendo el proyecto.


---

## Empieza aquí

| Si eres... | Ve a |
|---|---|
| **nuevo y quieres verlo funcionar** | [Instalación](#instalación), y luego [Dos minutos](#empezar-en-dos-minutos) |
| **alguien evaluando si le sirve** | [examples/WALKTHROUGH.md](examples/WALKTHROUGH.md) — un problema de punta a punta, siete comandos, quince segundos |
| **alguien buscando el comando para su pregunta** | [Qué comando responde a qué pregunta](#qué-comando-responde-a-qué-pregunta) |
| **un LLM al que le piden usar esto** | [Qué comando responde a qué pregunta](#qué-comando-responde-a-qué-pregunta), luego [El DSL](#el-dsl) y [Servidor MCP](#servidor-mcp). Corre [`certo lint`](#lint-antes-de-gastar-el-cómputo) sobre cada spec antes de ejecutarlo. |
| **alguien preguntándose qué NO hace** | [Qué no hace](#qué-no-hace) — tan importante como la lista de comandos |

## Qué comando responde a qué pregunta

Formulado como la pregunta, porque así es como llega cualquiera.

### ¿Es cierto?

| Tu pregunta | Comando | Qué vuelve |
|---|---|---|
| ¿Es cierta esta afirmación, bajo estas hipótesis? | `prove` | una demostración, o un **contraejemplo con valores concretos** |
| ¿Cuáles de mis hipótesis necesita de verdad? | `core` | el conjunto minimal, y cuáles sobraban |
| Mismas hipótesis, varias afirmaciones: ¿cuál necesita qué? | `core` sobre un `MultiSpec` | una tabla hipótesis-por-objetivo |
| ¿Es cierta esta desigualdad, con los multiplicadores a la vista? | `farkas` | `linarith`/`nlinarith`, **sin solver** |
| ¿Vale esto para todo `n ≥ n₀`? | `induct` | casos base + paso, **y la comprobación de que la cadena une** |

### ¿Está siquiera bien planteado mi problema?

| Tu pregunta | Comando | Qué vuelve |
|---|---|---|
| **¿Mi régimen no es vacío?** | `check --hypotheses-only` | un **modelo** si no lo es, el **choque minimal** si lo es |
| ¿Está bien planteado este spec, antes de gastar el cómputo? | `lint` | hipótesis contradictorias, una familia vacía, un dominio de 10⁹ |
| ¿Dónde está mi proyecto entero? | `status` | probado, pendiente, hueco, desfasado |
| ¿Puede esta instalación hacer lo que necesito? | `doctor` | cada capacidad, y qué cuesta cada hueco |

### ¿Cuánto, cuán pequeño, cuántos?

| Tu pregunta | Comando | Qué vuelve |
|---|---|---|
| ¿Cuál es el óptimo, exacto? | `opt` | el **dual racional exacto** = el certificado |
| ...¿y es óptimo de verdad sobre los enteros? | `mixed --prove-optimal` | branch and bound, **cada hoja certificada** |
| ¿Dónde está el umbral de esta constante? | `bisect` | el par que lo acota, cada lado certificado |
| ¿Es cierta esta desigualdad numérica? (`e`, `log`, `π`, `ζ`) | `bounds` | un encierro riguroso en racionales exactos |
| ¿Decae este término en `n`, o es Θ(1)? | `order` | el **exponente**, sin solver |
| Lo comprobé para `p = 5..12`. ¿Vale para TODO `p`? | `parametric` | una cota demostrada para toda la familia, desde un dual |

### ¿Vale para todos los casos?

| Tu pregunta | Comando | Qué vuelve |
|---|---|---|
| ¿Vale para todo grafo de `n` vértices? | `sweep` | la familia, **y qué se estableció sobre el predicado** |
| ...¿para todo elemento de cualquier dominio finito? | `cases` (`DomainSpec`) | lo mismo, sobre cualquier cosa enumerable |
| ¿Es insatisfacible esta CNF? | `cases` | una **prueba DRAT** |
| Mi contraejemplo es enorme: ¿cuál es el de verdad? | `shrink` | un testigo minimal, con el descenso registrado |
| Mil fallos: ¿cuántos objetos son en realidad? | `sweep --witnesses` | órbitas, y un testigo minimal por órbita |

### Álgebra y números

| Tu pregunta | Comando | Qué vuelve |
|---|---|---|
| ¿Tienen solución estas ecuaciones polinómicas? | `ideal` | cofactores de Gröbner, comprobables expandiendo |
| Quítame `t` y dime la condición sobre `s` | `eliminate` | la **resultante**, con `Res = A·f + B·g` adjunta |
| ¿Es este polinomio no negativo en todas partes? | `sos` | cuadrados racionales exactos, sin solver |
| ¿Es primo este entero? | `number` | un árbol de Pratt, comprobable por exponenciación modular |

### Construir y conservar

| Tu pregunta | Comando | Qué vuelve |
|---|---|---|
| ¿Existe un objeto con estas propiedades? | `synth` | CEGIS, más los contraejemplos que lo forzaron |
| ¿Cómo ensamblo mis lemas en una demostración? | `compose` | la demostración, **con cada puente nombrado** |
| ¿Sigue siendo válido este certificado guardado? | `verify` | re-comprobado, con los avisos repetidos |
| Llevar esto a Lean | `export --lean` | enunciados reales para aritmética lineal; datos para grafos |
| ¿Qué corrí el mes pasado? | `ledger` | un registro auditable, re-verificable |

Tabla completa con motores y tipos de certificado:
[Los veintisiete comandos](#los-veintisiete-comandos).

## Qué es y qué no es

**Es** el instrumento de laboratorio: encontrar una contradicción rápido,
saber qué hipótesis sobran, validar exhaustivamente un caso finito, acotar una
constante con certificado, sintetizar un candidato sobre un dominio acotado.

**No es** un asistente de pruebas —eso son Lean, Rocq o Isabelle— ni un
catálogo de álgebra computacional. Ver [Qué no hace](#qué-no-hace), que importa
tanto como la lista de comandos.

**El reparto de funciones**, en palabras de un usuario tras una sesión real:
certo encuentra y certifica los trades pequeños; la demostración humana explica
por qué ensamblan globalmente sin doble cobro.

## La comprobación que tu asistente de pruebas no puede hacer por ti

Lean demostrará tu teorema, no reportará ningún `sorry`, y `#print axioms`
saldrá limpio. Nada de eso te dice que las hipótesis fueran satisfacibles.

Un usuario lo formuló exactamente: `#print axioms` certifica *«no hice
trampa»*. No dice nada de *«esto no es hueco»*. Tenía dos módulos Lean —sin
`sorry`, axiomas `[propext, Classical.choice, Quot.sound]`, todo lo que una
formalización debe aparentar— y **los dos tenían el régimen vacío**. Los
teoremas eran ciertos, válidos, y no iban de nada.

```
$ certo prove regimen.py
DEMOSTRADO -- simbólico y universal bajo las hipótesis  [unsat]
  VACUA: estas hipótesis se contradicen entre sí, así que este objetivo --y
  cualquier otro-- se sigue. La demostración es válida y no dice nada.
  El choque es: dens_alta, kappa_pequena
  !! las hipótesis son contradictorias: esta demostración es vacua
```

El veredicto no cambia —es una demostración de verdad, y de una contradicción
se sigue todo—. Lo que cambia es que te lo dicen, **y te dicen qué hipótesis
chocan**, de forma minimal, así que la siguiente pregunta ya está respondida.

Y se sigue diciendo. La marca y el conjunto en conflicto viajan en el
certificado, así que `verify` lo repite meses después, cuando solo queda el
artefacto.

Se comprueba en cada `prove`, `core`, `farkas` y `compose` que sale bien, al
coste de una llamada extra al solver sobre un problema estrictamente más
fácil que el que se acaba de resolver.

### Y la otra mitad: una refutación con modelo

El mismo usuario escribió que una restricción de densidad «obliga a `G` casi
completo, luego es trivial». `certo prove` lo refutó en 15 ms con
`dens = 27/32` factible. Luego que con `|κ| ≥ 4` bastaba para toda densidad
—refutado con `dens = 127/128, |κ| = 7`, fallando por `0.3351` frente a
`0.3333`—. La cota correcta era 8.

Las dos habrían ido a una pasada de formalización. Dos de esas, a dos horas y
media cada una, en una línea que ya había producido cuatro regímenes vacíos.


## Instalación

Requiere Python 3.11+.

```bash
pip install -e ".[mcp,numerics]"
```

Dependencias: `z3-solver` y `pulp`, que traen sus propios binarios. Los extras
son `mcp` para el servidor MCP y `numerics` para `bounds` y `sos`
(`python-flint`, `mpmath` y `numpy`); sin ellos queda el CLI, menos la
numérica rigurosa y las sumas de cuadrados.

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
| `numpy` | la búsqueda de Gram tras `sos` | **nada** — `sos` no puede correr sin él |

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

## Los veintisiete comandos

| Comando | Qué hace | Motor | Certificado |
|---|---|---|---|
| `prove` | Niega la tesis y busca `unsat` | Z3 | núcleo insatisfacible, o contraejemplo |
| `check` | Satisfacibilidad; `--hypotheses-only` pregunta si el régimen no es vacío | Z3 | modelo, o núcleo |
| `core` | MUS: qué hipótesis hacen falta | Z3 | núcleo minimal |
| `farkas` | `linarith` / `nlinarith`, con los multiplicadores | LP exacto | **certificado de Farkas**, sin solver |
| `compose` | Ensambla lemas en una demostración, comprobando el empalme | Z3 | **proof**: cada lema, su certificado y el enlace |
| `induct` | Casos base + un paso, y la comprobación de que la cadena se junta | Z3 | **induction**: las dos mitades y los dos números que importan |
| `synth` | CEGIS: ∃obj ∀entrada ∃aux | CEGIS/Z3 | objeto + contraejemplos que lo forzaron |
| `opt` | LP/ILP, o un packing | CBC | **dual exacto** = el certificado de cargas |
| `mixed` | Un esqueleto discreto buscado, la parte continua certificada | CBC + LP exacto | **diseño mixto**: asignación, dual exacto y una cota |
| `order` | El exponente de `n` tras sustituir magnitudes: ¿decae, o Θ(1)? | Laurent exacto | **el exponente**, sin solver |
| `bounds` | Una desigualdad numérica, con rigor (`e`, `log`, `π`, `ζ`) | Arb o mpmath | **envolvente en racionales exactos** |
| `ideal` | Sistemas polinómicos: refutarlos, o certificar lo que se sigue | Gröbner, propio | **cofactores**, comprobados expandiendo |
| `eliminate` | Quitar una variable de dos polinomios; quedarse con la condición | Sylvester + Bareiss | **Res = A·f + B·g**, sin solver |
| `parametric` | Una cota para TODO valor de un parámetro, desde un dual que ya tienes | dualidad débil, simbólica | **y y los residuos desplazados**, sin solver |
| `sos` | Un polinomio es no negativo, como suma de cuadrados | numérico + redondeo exacto | **cuadrados racionales**, sin solver |
| `number` | Primalidad, o una factorización | Pratt | **árbol de exponenciación modular** |
| `cases` | SAT con prueba DRAT verificada | CDCL propio o binario externo | prueba DRAT |
| `enum` | Grafos no isomorfos con filtros | nauty o Python | lista canónica + hash |
| `sweep` | Predicado y/o magnitud sobre una familia o CUALQUIER dominio finito | nauty o Python | familia **+ certificados del predicado** |
| `shrink` | Minimiza un contraejemplo (grafo o MUS) | CDCL / reducción | testigo de minimalidad |
| `bisect` | Umbral de una constante | prove o cases | el par que lo encierra |
| `lint` | Comprobar un spec antes de gastar el cómputo en él | — | — |
| `status` | Dónde está una demostración: probado, pendiente, hueco, desfasado | — | — |
| `doctor` | Qué puede hacer esta instalación y qué cuesta cada hueco | — | — |
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
| `InductSpec` | `induct` |
| `IdealSpec` | `ideal` |
| `EliminateSpec` | `eliminate` |
| `ParametricSpec` | `parametric` |
| `SOSSpec` | `sos` |
| `NumberSpec` | `number` |
| `BoundSpec` | `bounds` |
| `OrderSpec` | `order` |
| `BisectSpec` | `bisect` |

El esquema de certificados está **congelado desde 0.4**: los payloads
existentes no se mueven, así que un certificado hecho para un paper sigue
verificando contra un certo posterior. Los tipos nuevos siguen siendo
aditivos, y lo seguirán siendo.

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
| `asymptotic` | el exponente de un parámetro en un término | **sí**, aritmética exacta |
| `ball` | una cantidad real cae en un intervalo, y eso zanja la afirmación | **sí** para la afirmación; el intervalo necesita la spec |
| `proof` | los lemas **y** que cada uno se usa como su certificado permite | no, re-resuelve |
| `induction` | los casos base, el paso **y** que encadenan sin hueco | no, re-resuelve |
| `mixed_design` | una construcción existe y alcanza un valor; NO que sea óptima | **sí**, aritmética exacta |
| `ideal` | `f = Σ hᵢgᵢ` | **sí**, expandir un producto |
| `resultant` | `Res = A·f + B·g` | **sí**, expandir dos productos |
| `parametric_bound` | `opt(p) ≤ b(p)·y` para todo p | **sí**, expandir y leer signos |
| `sos` | `p = Σ dᵢqᵢ²` en racionales exactos | **sí**, expandir un producto |
| `number` | primalidad, o una factorización | **sí**, exponenciación modular |
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

## `induct`: casos base, un paso, y el hueco entre ambos

«Comprobado a mano hasta n = 8, y de ahí por inducción» es como acaba una
buena parte de los argumentos combinatorios. Las dos mitades ya tenían
comando —`sweep` o `cases` para la base, `prove` para el paso— y el empalme
quedaba en una frase.

Ese empalme no es decoración. Una base que cubre 3..8 con un paso válido solo
desde k ≥ 10 no demuestra **nada** sobre n = 9, y la frase se lee idéntica en
los dos casos.

```python
InductSpec(
    k0=3, base_upto=8,
    base=lambda j: spec_en(j),        # Spec, SweepSpec, DomainSpec o un cert
    step=step_spec,                   # asume P(k), k >= 3; afirma P(k+1)
    step_from=3,
)
```

```
$ certo induct examples/induct_sum.py
PROVED  [unsat]
  6 base cases k=3..8, step from k=3, chained by induction
```

### Z3 no hace inducción, y esto no finge lo contrario

Un solver SMT no tiene esquema de inducción y no lo va a tener. El principio
se aplica **aquí**, y la estructura del certificado *es* esa aplicación.
`verify` lo dice todas y cada una de las veces:

> La inducción sobre los naturales se APLICA aquí, no la verifica un solver.
> Es un esquema fijo, a diferencia de un puente, pero sigue siendo un paso que
> ningún certificado de este fichero realiza.

Es un tipo de paso distinto del puente de `compose`: los puentes son
afirmaciones sobre lo que *significa* un cómputo concreto y cambian con cada
problema, mientras que la inducción sobre los naturales es un esquema fijo y
con nombre. Por eso queda registrado en vez de advertido — pero queda
registrado.

### Qué se comprueba de verdad

```
$ certo verify out/induct.json
  [ok] the base cases are exactly k0..base_upto  (k=3..8, 6 cases present)
  [ok] the step starts no later than the base ends  (step from k=3, base reaches 8)
  [ok] base case k=3 holds   ... k=4 ... k=5 ... k=6 ... k=7 ... k=8
  [ok] the inductive step holds
  [ok] the step certificate entails the step statement
```

Las dos primeras son la razón de correr esto. Pon `step_from=10` y se niega en
tiempo de construcción —no se escribe certificado— y si alguien falsifica uno
después, la verificación lo vuelve a pillar:

```
[XX] the step starts no later than the base ends  (step from k=10, base reaches 8)
[XX] the base cases are exactly k0..base_upto     (k=3..8, 5 cases present)
```

El paso se demuestra con el índice **libre**, que es lo que lo hace
universalmente válido: una demostración con una variable libre es una
demostración para todos sus valores, así que no hay cuantificador que darle a
un solver.

## Tipos combinatorios nativos

Familias de conjuntos, hipergrafos, diseños y sistemas de máscaras se estaban
recodificando a mano en cada spec: una tupla de frozensets aquí, máscaras
allá, un `key` para el id, un `canonicalize` para cocientar, un `reduce` para
minimizar. Cuatro trozos de andamiaje por problema, y cada uno un sitio donde
equivocarse sutilmente.

```python
from certo import DomainSpec, SetFamily

def spec():
    return DomainSpec(
        items=lambda: list(SetFamily.all_families(5, 2, 3)),
        predicate=lambda f: f.intersecting(),
        canonicalize="auto", reduce="auto",      # y ningún key=
    )
```

```
REFUTED: 90 counterexamples out of 120 examined -- 90 labelled, 2 up to symmetry
  5:01|02|13  x60
  5:01|02|34  x30
```

Lo valioso de un tipo nativo aquí no es que guarde datos —eso lo hace una
tupla—. Es que aporta las tres cosas que el resto de la herramienta pide:
`key()`, `canonical()` y `reductions()`. Así `key`, `canonicalize` y `reduce`
se pueden dejar todos en `"auto"`, y cualquier clase propia se suma sin más
que tener esos métodos.

| | |
|---|---|
| `is_design(t, λ)` | todo t-subconjunto en exactamente λ bloques |
| `is_uniform(k)`, `is_regular(r)` | los dos de siempre |
| `intersecting()` | todos los pares de bloques se cortan — la forma de Erdős–Ko–Rado |
| `covers()` | todo punto usado |
| `SetFamily.all_families(n, k, size)` | el dominio a barrer |
| `family_from_masks(n, masks)` | un sistema de máscaras, con id y forma canónica |

### La forma canónica es exacta, o se niega

Dos familias tienen la misma forma canónica **exactamente cuando** un
reetiquetado del conjunto base lleva una a la otra. Los puntos se refinan en
clases que ningún reetiquetado puede mezclar —grado, luego los tamaños de los
bloques que pasan por cada punto, luego lo mismo otra vez sobre las clases
refinadas— y se minimiza sobre las permutaciones que respetan ese refinamiento.

En una familia muy regular eso degenera hacia n!, así que hay un tope. Y
alcanzarlo **levanta un error** en vez de caer a un invariante más barato: un
invariante que fusionara dos familias no isomorfas fusionaría dos órbitas, y
nada aguas abajo se daría cuenta.

## Simetrías en barridos de grafos

`SweepSpec` también acepta `canonicalize`. El enumerador ya devuelve un grafo
por clase de isomorfía, así que ahí `"auto"` no aporta nada — es para una
simetría **más fina** que la isomorfía (grafos coloreados, enraizados o
decorados de otro modo) y para familias que no produjo el enumerador.

## Simetrías: tres respuestas en vez de mil

Una búsqueda combinatoria produce copias reetiquetadas del mismo objeto a
cientos. Un barrido que informa de 1.400 contraejemplos donde hay cuatro
estructurales no te ha dicho cuatro cosas y las ha enterrado — te ha dicho una
cosa 1.400 veces y te ha dejado a ti la lectura.

Declara cuándo dos elementos son el mismo objeto reetiquetado:

```python
DomainSpec(
    items=[(a, b, c) for a in range(1, 5) for b in range(1, 5)
           for c in range(1, 5)],
    predicate=lambda t: sum(t) != 6,
    key=lambda t: "({},{},{})".format(*t),
    canonicalize=lambda t: tuple(sorted(t)),      # la simetría
)
```

```
$ certo sweep examples/sweep_orbits.py
REFUTED  [sat]
  REFUTED: 10 counterexamples out of 64 examined -- 10 labelled, 3 up to symmetry
  10 contraejemplos, 3 salvo simetría
  órbitas (de los contraejemplos):
    (1,2,3)   x6   (1,2,3), (1,3,2), (2,1,3)
    (1,1,4)   x3   (1,1,4), (1,4,1), (4,1,1)
    (2,2,2)   x1   (2,2,2)
```

Nada aquí sabe cuál es el grupo, y no le hace falta: le hace falta saber
cuándo dos elementos son iguales. El representante es el de id más pequeño;
regla arbitraria, pero **determinista**, así que dos ejecuciones nunca
producen certificados que parezcan contradictorios diciendo lo mismo.

Solo se descomponen los **contraejemplos**. La estructura de órbitas de todo
lo que pasó rara vez es la pregunta, y calcularla sobre un dominio grande no
es gratis.

### Dónde está la línea de honestidad

Que dos elementos con la misma forma canónica estén de verdad en la misma
órbita es una **afirmación de la spec**. `canonicalize` es Python arbitrario y
nada aquí lo puede comprobar. Lo que `verify` sí comprueba es que la
descomposición se sostenga:

```
  [ok] the orbits partition the domain  (3 orbits covering 10 of 10 items)
  [ok] each orbit has its own representative  (0 representatives appear twice)
  [ok] each representative belongs to its orbit
```

Una descomposición cuyas partes no cuadran está mal fuera cual fuera el grupo.

## Reductores estándar

`shrink` tiene que saber qué significa «un paso más pequeño», y antes exigía
un `reduce` escrito a mano. Honesto, y también fricción. Las formas que se
repiten ya tienen nombre:

| `reduce=` | Hace |
|---|---|
| `"auto"` | elige según el tipo del elemento, o **se niega** |
| `"sets"` | quita un elemento |
| `"sequences"` | quita un elemento de una lista o tupla |
| `"decrement"` | baja en uno una coordenada entera |
| `"graphs"` | borra un vértice |
| `"masks"` | apaga un bit |
| un callable | lo que escribiste — intacto |

`auto` trata una tupla de enteros como un **punto de parámetros**, no como una
colección: `(3, 1)` se reduce a `(2, 1)` y `(3, 0)`, no a `(1,)` y `(3,)`.
Quitarle una coordenada a un punto de parámetros le cambia la aridad, que rara
vez es la reducción que alguien quería.

Y `auto` se niega ante un tipo que no reconoce en vez de inventarse algo. Un
testigo minimal para la relación equivocada se ve exactamente igual que uno
minimal para la correcta, y nada aguas abajo se daría cuenta.

## `certo doctor`

Instalar todos los extras arrastra una cadena de dependencias considerable, y
la mayoría de la gente no necesita ninguno. Así que la respuesta a «¿qué tengo
realmente?» no debería leerse de un error de importación a mitad de una
ejecución.

```
$ certo doctor
  capability   present   what for
  python       [ok]      the interpreter (3.11 or newer)
  z3           [ok]      prove, check, core, synth, compose
  pulp         [ok]      opt, farkas (the exact LP behind both)
  flint        [ok]      bounds, with special functions
  nauty        [--]      fast graph enumeration for enum and sweep
  cadical      [--]      cases on large CNFs

  optional pieces missing, each with a fallback:
    nauty        the built-in Python engine, comfortable to n=8
    cadical      the built-in CDCL: correct, and slow

  MCP server
    workspace: /ruta/al/proyecto
    the server module imports and starts

  everything required is present
```

Cada fila dice tres cosas, y la tercera es la que importa: **qué pasa sin
ella**. Que falte una herramienta opcional casi nunca es fatal aquí, y una
lista de cruces rojas que no lo diga se lee como una instalación rota.

```bash
certo doctor --register-mcp
```

Añade `certo` al `.mcp.json` del directorio actual, **fusionando** con lo que
ya hubiera registrado en vez de reemplazarlo, y se niega a tocar un fichero que
no sea JSON válido. Además comprueba que el servidor arranca de verdad, que es
otra pregunta distinta de si está registrado — y la que la gente quiere decir.

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

## `mixed`: certificar la construcción, no la búsqueda

Un MILP que elige una estructura discreta *y* un packing fraccional
compatible a la vez es una forma que `opt` no podía expresar: `LPSpec(integer=
True)` hace enteras **todas** las variables, que es otro problema, no una
restricción de este. Las variables llevan ahora un tipo:

```python
lp.variable("y17", kind="binary")     # reservar este triángulo
lp.variable("q42")                    # empaquetar fraccionalmente en lo que queda
```

Lo importante es qué queda certificado. Para una **prueba de existencia**, si
la elección discreta era óptima da igual — exhibir una construcción que
alcance el objetivo es todo el trabajo. Así que el flujo deliberadamente no es
«certificar el MILP»:

```
búsqueda (CBC, heurística)  →  congelar la parte discreta
                            →  LP residual sobre la parte continua
                            →  dual exacto, todo exacto
                            →  comparar contra el objetivo
```

```
$ certo mixed examples/mixed_design.py --target 10
SATISFIABLE  [sat]
  certified design reaching 28/3, target 10
  alcanzado 28/3 = 6 discreto + 10/3 continuo | cota de relajación 28/3
  3 elecciones discretas: y0, y2, y3
  el valor alcanzado iguala la cota de relajación, así que ESTE es el óptimo global
```

### Tres números, separados

| | Qué es |
|---|---|
| **alcanzado** | lo que consigue esta construcción. Exacto, y una cota **inferior** genuina del óptimo verdadero, porque la cosa existe |
| **condicional** | lo mejor que puede hacer la parte continua **con este esqueleto**, del dual exacto del LP residual |
| **cota** | la relajación sobre **todos** los esqueletos: una cota **superior** |

Ese tercer número no está en el diseño obvio y cuesta un LP extra. Compra algo
real: **cuando `alcanzado` iguala `cota`, la optimalidad MILP global queda
certificada gratis.** Pasa más de lo que uno espera, y cuando no pasa, el hueco
se imprime en vez de dejarlo deducir del silencio.

### Qué se certifica y qué no

```
$ certo verify out/mixed.json
VALID  mixed_design certificate (verified without a solver)
  [ok] the discrete assignment really is discrete
  [ok] the full point satisfies every original constraint
  [ok] it attains the value it claims
  [ok] the residual LP's own certificate holds
  [ok] and that residual IS the original problem with this assignment substituted
```

Esa cuarta comprobación es la que hace que esto sea más que tres ficheros en
una carpeta. Sin ella el subcertificado podría ser de *otro* problema — el
mismo hueco que `compose` cierra entre un lema y el enunciado con que se usa.

La respuesta de CBC es una **conjetura hasta que algo la comprueba**: devuelve
`0.9999997` para un binario tan a menudo como no, así que la asignación se
redondea y luego se verifica contra las restricciones originales en aritmética
exacta. Un diseño que no sobrevive a esa comprobación se rechaza, no se
reporta.

Y cuando las cotas no se juntan:

> **NO SE AFIRMA OPTIMALIDAD GLOBAL.** El esqueleto discreto salió de una
> búsqueda que aquí no se rehace; lo certificado es que esta construcción
> existe y alcanza lo que dice.

### Quedarse corto no es un certificado inválido

Un diseño que no llega a su objetivo verifica como **VALID** con un aviso. El
certificado es correcto; el diseño es insuficiente, y son afirmaciones
distintas. Leer `INVALID` ahí diría que algo está roto cuando no lo está.

La optimalidad MILP completa —un certificado de branch-and-bound con dual
exacto o prueba de infactibilidad en cada hoja— es otra cosa, y mucho mayor.
Está en el backlog, y no es lo que necesita una prueba de existencia.

### Tres niveles, con nombre

Un usuario pidió exactamente esta taxonomía, con estas palabras, y los nombres
son lo que necesita quien lee:

| Nivel | Qué se sostiene |
|---|---|
| `feasible` | un punto mixto satisface toda restricción y alcanza un valor |
| `conditional_optimum` | y el LP residual es óptimo **dado este esqueleto** |
| `global_optimum` | e iguala la cota de relajación, así que ningún esqueleto lo mejora |

```
$ certo verify out/mixed.json
VALID  mixed_design certificate (verified without a solver)
  ...
  ÓPTIMO GLOBAL: iguala la cota de relajación, así que ningún esqueleto lo mejora
```

### `--freeze`: tu solver, no el nuestro

Un MILP real puede resolverlo HiGHS, Gurobi, algo a medida o una persona.
Exigir que el CBC de certo lo reproduzca pondría **los límites de certo
delante de una construcción que ya existe**, que es al revés.

```bash
certo mixed spec.py --freeze mi_solucion.json --target 602/9
```

El fichero es `{"y17": 1, "y23": 0, ...}` — o `{"assignment": {...}}`. Se
redondea y se comprueba exactamente igual que cualquier otro, así que de dónde
venga no cambia nada de lo certificado. Lo que sí cambia queda registrado:

> El esqueleto vino de **otro solver** y aquí se congeló. Eso no cambia nada
> de lo certificado —se redondeó y comprobó exactamente igual que cualquier
> otro— pero significa que certo no vio la búsqueda que lo produjo.

## `opt --target`

Para una prueba de existencia la pregunta rara vez es «cuál es el mejor valor
posible» y casi siempre «se alcanza esta cota»:

```
$ certo opt examples/packing_mixed.py --target 12
  25/2 REACHES the target 12
```

El objetivo viaja en el certificado, así que `verify` repite la comparación en
racionales exactos:

```
  [ok] the certified value reaches the target  (25/2 against 12, margin 1/2)
```

Quedarse corto es un **aviso sobre un certificado válido**, no invalidez — el
certificado es correcto y la cota es insuficiente, y son afirmaciones
distintas.

## Entero en un tipo, fraccional en otro

```python
PackingSpec(items=..., integer={"K3"})     # triángulos enteros, K4 fraccionales
```

`integer=True` sigue significando todos. Un packing cuyos ítems estructurales
se colocan enteros mientras el resto es una relajación fraccional es la forma
habitual, y forzar todo-o-nada cambia el problema en vez de restringirlo.

En un problema así `opt` reporta **solo la cota de relajación** y lo dice:
redondear todas las variables convertiría un peso de K4 de 1/6 en cero y
reportaría un diseño que no vale nada. El valor alcanzable sale de congelar la
parte discreta y reresolver el resto, que es `certo mixed`.

## Tres motores que no son un solver

`prove`, `check`, `core`, `synth` y `compose` son Z3 con distintos sombreros.
Estos tres no, y existen porque las preguntas que responden son de las que un
solver SMT o mastica sin fin o no sabe ni formular.

### `ideal` — sistemas polinómicos, decididos algebraicamente

```python
IdealSpec(
    variables=["x", "y"],
    equations=[x*x + y*y - 1, x - y, x + y - 3],
    claim=None,                    # None: ¿es inconsistente el sistema?
)
```

```
$ certo ideal examples/ideal_inconsistent.py
PROVED  [unsat]
  the system has NO common solution: 1 is in the ideal, and the cofactors prove it
  cofactores:
    g0 * (2/7)
    g1 * (2/7*y - 3/7)
    g2 * (-2/7*x - 3/7)
```

Multiplica eso y sale `1`. Esa es toda la demostración, y comprobarla es
expandir un producto y comparar coeficientes en racionales exactos — **sin
solver, sin sistema de álgebra, sin nada que creerse.** Encontrar los
cofactores es un cómputo de base de Gröbner; una biblioteca que solo te dice
«sí, está en el ideal» te deja únicamente con su palabra.

Con un `claim`, la misma maquinaria certifica `f = Σ hᵢgᵢ`: que `f` se anula en
toda raíz común.

Dos propiedades que conviene saber:

* **Decide.** La pertenencia por bases de Gröbner es decidible, así que una
  respuesta negativa es `REFUTED`, no `unknown_solver`. Eso es raro en esta
  herramienta y vale la pena usarlo: `prove` sobre un sistema de igualdades
  polinómicas puede atascarse donde esto responde.
* **El cuerpo es ℂ.** `1 ∈ I` refuta soluciones sobre los complejos, luego
  también sobre reales, racionales y enteros. El recíproco **no** vale: un
  ideal propio significa que hay raíz compleja, y no dice nada de una real.
  `verify` lo repite cada vez.

### `sos` — búsqueda numérica, certificado exacto

Argumenté dos veces en las notas de este proyecto que las sumas de cuadrados
no valían la pena, porque un SDP se resuelve en coma flotante y un certificado
inexacto no es citable. Esa objeción apuntaba a la mitad equivocada. Dejaría
fuera también a `opt` — y `opt` la responde: resolver numéricamente,
reconstruir racionales, re-verificar exacto.

```
$ certo sos examples/sos_quartic.py
PROVED  [unsat]
  a sum of 2 squares, exact, with denominator 2
  cuadrados:
    1 * (-1/2*x^2 + y^2)^2
    3/4 * (x^2)^2
```

El proceso: escribir `p = zᵀGz` (una condición lineal sobre `G`), encontrar una
`G` numérica por proyecciones alternas sobre ese subespacio afín y sobre el
cono PSD, redondearla, **volver a proyectarla sobre el subespacio de forma
exacta en `Fraction`**, y hacer una LDLᵀ exacta. Si todos los pivotes son no
negativos, la descomposición *es* la suma de cuadrados. Los flotantes eran la
búsqueda; no llegan al certificado.

Incompleto, y de una forma que conviene conocer: toda suma de cuadrados es no
negativa, pero desde grado 4 en 3 variables hay polinomios no negativos que no
son suma de cuadrados. El de Motzkin es el habitual, y `certo sos` devuelve
`unknown_solver` con él — nunca «el polinomio se hace negativo».

Para grado 2, `farkas --nonlinear` es más barato y llega antes.

### `number` — primalidad citable

`n.is_prime()` es cierto, rápido e incitable. Un certificado de Pratt es el
mismo hecho con la evidencia pegada:

```
$ certo number --n 2147483647
PROVED  [unsat]
  2147483647 is prime, with a Pratt certificate of 53 modular checks
  witness: 7
  árbol de Pratt: 29 nodos, profundidad 5
```

`n` es primo exactamente cuando algún `a` genera `(ℤ/n)*`: `a^(n−1) ≡ 1` y
`a^((n−1)/q) ≢ 1` para todo primo `q | n−1`. Esos `q` también necesitan
certificado, así que la cosa es un **árbol** que recursa hasta el 2 — y
comprobarlo entero son un puñado de `pow(a, e, n)`.

Tres detalles que separan un certificado de un test:

* **La lista de factores tiene que estar completa.** Saltarse un factor primo
  de `n−1` dejaría pasar un compuesto, así que `verify` comprueba que los
  factores multiplican de vuelta a `n−1` antes de mirar el testigo.
* **Números de Carmichael.** 561 pasa la condición de Fermat para casi
  cualquier base; lo que lo caza es la condición de orden, y
  `certo number --n 561` sale `REFUTED` sin certificado.
* **El testigo es reproducible.** Se prueban bases pequeñas en orden, no al
  azar, así que el mismo `n` da el mismo certificado —y el mismo digest— en
  cualquier máquina.

`--question factor` da la factorización, con cada factor llevando su propio
certificado de primalidad, para que «y estos son primos» no quede colgando.

## `parametric`: ¿comprobado para p = 5..12, o cierto para todo p?

Esto es lo que certo insistía en que no podía hacer, y la frase que más peso
sin ganar carga en la escritura matemática: *«y análogamente para n mayor»*.

Para un programa lineal cuyos datos son **polinomios** en un parámetro, la
dualidad débil está disponible simbólicamente. Cualquier `y >= 0` con
`A(p)ᵀy >= c(p)` da `opt(p) <= b(p)·y` —para todo `p` a la vez, no para los
que corriste—.

```
$ certo parametric examples/parametric_bound.py
DEMOSTRADO  [unsat]
  para todo p >= 10, el óptimo es a lo sumo 1/6*p^2 + 1/6*p - 2/3
  y eso es todo valor con p >= 10 --no una muestra de ellos--
```

Y no es una cota floja. Resolviendo ese LP directamente:

| p | cota | óptimo |
|---|---|---|
| 10 | 53/3 | 53/3 |
| 11 | 64/3 | 64/3 |
| 15 | 118/3 | 118/3 |
| 30 | 463/3 | 463/3 |

**Un dual, leído de una sola instancia resuelta en `p = 10`, da el óptimo
exacto para todo `p` por encima.**

### El reparto de trabajo

certo no busca `y` aquí. `certo opt` sobre una instancia te da uno, y
cualquier otro solver también. Lo que esto comprueba es que el `y` que ya
tienes sirve para toda la familia —y esa comprobación es aritmética—:

> sustituye `p = 10 + u`, expande, y lee los signos de los coeficientes

Todos no negativos significa que el polinomio es no negativo sobre el rayo,
porque `u` y sus potencias lo son. El mismo reparto que `farkas`, un nivel más
arriba: allí los multiplicadores son constantes, aquí son constantes pegadas a
una familia.

### Qué no va a fingir

El test del desplazamiento es **suficiente y no necesario**. `p² - 3p + 3` es
positivo en todas partes y falla en `p₀ = 0`. Así que un fallo significa *«no
establecido por esta ruta»*, nunca *«falso»* —y **no se emite certificado**,
porque una ruta que no funcionó no es una cota—.

`verify` repite el resto siempre: esto acota la **relajación LP**, no dice
nada por debajo del piso, y no dice nada sobre un óptimo entero.

### De dónde salió

Una instancia real, y la estructura merece verse. Un LP simetrizado resuelto
exactamente para `p = 5..12` con un simplex racional escrito a mano dio duales
**constantes a trozos con umbrales** —un vértice en `p = 6`, otro en
`p = 7, 8, 9`, un tercero desde `p = 10`—. En cada trozo la cota es un
polinomio en `p` y el dual es fijo, que es exactamente la forma que este
comando certifica. Los umbrales son parte de la respuesta, no algo que
disimular.


## `eliminate`: quita una variable, quédate con la condición

`ideal` dice qué se sigue de un sistema. Esto responde la otra pregunta que se
hace uno montándolo: **quítame `t` y dime qué tiene que cumplir `s`.**

```
$ certo eliminate examples/eliminate_parameter.py
SATISFACIBLE  [sat]
  eliminada t. Solo hay raíz común donde esto se anula: -4*s^3 + 1
  degrees: 3 and 2 in t
  certificado: resultant (no necesita solver)
```

La respuesta es la **resultante**: un polinomio en las variables restantes que
se anula exactamente cuando las dos comparten raíz en `t`. Ese ejemplo está
elegido para que lo compruebes a mano —sustituye `t² = s` en `t³ + st + 1` y
queda `2st + 1`, luego `t = -1/(2s)`, y de vuelta en `t² = s` sale `4s³ = 1`—.

Lo que viaja no es el número sino la **identidad de Bézout**:

```
$ certo verify out/elim.json
VÁLIDO  certificado resultant (comprobado expandiendo dos productos, sin solver)
  [ok] Res = A*f + B*g, expandiendo  (resultante: -4*s^3 + 1)
  [ok] los cofactores de Bézout tienen los grados que les da la construcción
```

Calcular una resultante es un determinante sobre un anillo de polinomios;
comprobarla es expandir dos productos y restar. Esa brecha es toda la razón de
que sea un certificado y no «el sistema de álgebra estuvo de acuerdo». El
determinante es Bareiss —libre de fracciones, donde cada división es una
división de polinomios cuyo resto se **comprueba que es cero** en vez de
suponerlo—.

### Una constante no nula es una refutación

```
$ certo eliminate sin_raiz_comun.py
REFUTADO  [unsat]
  NO hay raíz común en t, para ningún valor de las demás variables, sobre
  ningún cuerpo: la resultante es la constante no nula 1
```

Eso es concluyente en la dirección fuerte y cuesta un determinante.

### Qué no dice

`Res = 0` es **necesario** para una raíz común, sobre cualquier cuerpo. Es
**suficiente** sobre un cuerpo algebraicamente cerrado, y solo donde los
coeficientes líderes en la variable eliminada no se anulen los dos. Sobre los
reales una resultante nula puede significar una raíz común *compleja* y nada
más.

`verify` lo repite siempre, y cuando los dos coeficientes líderes pueden
anularse lo dice explícitamente: ese lugar es exactamente donde se pierde la
suficiencia.

**Exactamente dos polinomios**, porque eso es una resultante. Iterarla por
pares sobre un sistema mayor introduce factores extraños que nada aquí podría
certificar; para eso está `ideal`.


## `order`: ¿decae este término, o es Theta(1)?

Algunos bugs no son infactibilidades. Un usuario tenía este:

```
5|k| W C^2 / (u^3 d^2 p^10)
```

con `d ≍ n²`, `C ≍ n`, `|W| ≍ n²`. La pregunta era si decae en `n`. No decae
—es **Θ(1)**— y ese bug era invisible para Lean **y** para `certo prove`, por
la misma razón. No es una infactibilidad. Es una factibilidad que no mejora
con `n`, así que un solver al que preguntas «¿es satisfacible?» dice que sí
para siempre, correctamente, mientras la cota en la que vive no mejora nunca.

```python
OrderSpec(
    expression=5 * k * W * C * C / (u ** 3 * d ** 2 * p ** 10),
    orders={"k": 0, "W": 2, "C": 1, "u": 0, "d": 2, "p": 0},
)
```

```
$ certo order examples/order_decay.py
SATISFIABLE  [sat]
  leading exponent 0: it is Theta(1) in n

$ certo order examples/order_decay.py --expect decays
REFUTED  [sat]
  REFUTED: you claimed it decays, and it is Theta(1)
```

Lo que lo hace digno de un certificado y no solo de una cuenta es que **la
sustitución queda escrita** en vez de hecha en la cabeza de alguien, y que la
agrupación es exacta: dos términos con el mismo exponente cuyos coeficientes
se cancelan se cancelan de verdad, y con `Fraction` eso se decide, no se
estima.

Dos límites que declara en vez de esconder:

* **Certifica el exponente, no la constante.** `≍` esconde un factor, así que
  un término Θ(1) con coeficiente 1e-9 puede estar perfectamente bien en la
  práctica. `verify` lo repite todas las veces.
* **No se puede dividir por una suma.** El orden de `1/(x + y)` depende de
  cuál de `x` e `y` domine —una pregunta que esto no puede responder—, así que
  se niega en vez de adivinar.

Un símbolo sin entrada en `orders` es un **error**, no una suposición. Todo el
valor está en que la sustitución sea explícita.


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

## El modo exacto dejó de depender del dual de CBC

Un usuario certificó 56 LPs de forma exacta y **3 necesitaron que inyectara a
mano el primal y el dual racionales** —todos en soluciones simétricas—. Eso no
es mala suerte. En un vértice degenerado hay varios duales óptimos, CBC
devuelve uno arbitrario, y redondear *ese en concreto* puede no ser ni
dual-factible.

La solución no es una escalera de denominadores más larga. Dado un primal
exacto, la holgura complementaria determina el dual: `yᵢ = 0` en cada fila con
holgura, y `Σᵢ Aᵢⱼ yᵢ = cⱼ` para cada `j` con `xⱼ > 0`. Eso es un sistema
lineal sobre las filas tensas, resuelto en `Fraction` por eliminación
gaussiana sin un solo flotante. Donde lo deja subdeterminado —más filas tensas
que variables activas, que es justo lo que produce la simetría— la libertad
sobrante **es** el conjunto de duales óptimos, así que cada elección se ofrece
por turno.

```
max 2x + 3y   s.a.  x + y ≤ 1,  x + 2y ≤ 1,  x, y ≥ 0
```

Las dos filas están tensas en el óptimo y solo una variable está activa.
Certificarlo funciona ahora **sin ningún dual utilizable del solver**:

| lo que devolvió CBC | certifica | dual usado |
|---|---|---|
| nada (`0, 0`) | sí | `(0, 2)` |
| basura (`7.3, -2.1`) | sí | `(0, 2)` |
| el dual de otro vértice | sí | `(0, 1.5)` → `(0, 2)` |

Un dual derivado **no** se cree por ser derivado. Es un candidato, igual que
uno redondeado, y se gana el certificado pasando el mismo `check_lp` exacto.
Lo que cambia es de dónde salen los candidatos: de la estructura del problema
en vez de donde aterrizara un solver de flotantes.

La reconstrucción sigue corriendo primero, así que todo LP que certificaba
antes certifica igual, con el mismo denominador mínimo y el mismo digest.


## El comando más usado deja de necesitar solver

Un `unsat_core` decía «z3 estuvo de acuerdo conmigo», y `verify` volvía a
correr z3 para comprobarlo. Un usuario puso la objeción con precisión: *útiles,
pero no sin-solver como un certificado Farkas racional.*

Ahora es sin-solver siempre que el core sea aritmética lineal. Tras encontrar
el core, la búsqueda de Farkas corre sobre esas filas exactas, y los
multiplicadores viajan en el payload:

```
$ certo prove examples/farkas_linear.py --cert core.json
  certificado: unsat_core (no necesita solver)

$ certo verify core.json
VÁLIDO  certificado unsat_core (comprobado por aritmética, sin solver:
                                multiplicadores de Farkas)
  [ok] todos los multiplicadores son no negativos
  [ok] la combinación cierra: la suma de lambda_i * fila_i es una contradicción
```

Que la búsqueda use punto flotante no lo compromete. El LP es una forma de
**encontrar** los multiplicadores; `is_contradiction` los acepta o los rechaza
en aritmética exacta con `Fraction`, de forma independiente, así que una mala
conjetura se rechaza en vez de creerse. La misma disciplina de `opt` y `sos`.

El core sigue en el payload —`compose` lo lee para el chequeo de entailment— y
los multiplicadores son campos opcionales, que el esquema congelado permite.
Un lector de 0.5 verifica el certificado igual que antes.

### Y el export a Lean deja de decir `sorry`

Se reportaron como dos huecos distintos. Tienen un solo arreglo. Un core se
exportaba con `sorry` precisamente porque dice *qué* hipótesis bastan y no *por
qué*; con los multiplicadores sabe por qué:

```lean
theorem from_core (x y : ℝ)
    (x_ge_1 : 1 - x ≤ 0)
    (y_ge_1 : 1 - y ≤ 0)
    : -2 + x + y ≥ 0 := by
  linarith [x_ge_1, y_ge_1]
```

Un régimen vacuo se vuelve una demostración que compila de que está vacío:

```lean
theorem regime_empty (dens : ℝ)
    (dens_floor : (3/4 : ℚ) - dens ≤ 0)
    (sparse : (-1/2 : ℚ) + dens ≤ 0)
    : False := by
  linarith [dens_floor, sparse]
```

CI compila las dos contra Mathlib v4.28.0 en cada push. Fuera de la aritmética
lineal no cambia nada: sin multiplicadores, `sorry`, y el archivo dice por qué.


## ¿Mi régimen no es vacío? Pregúntalo directo

La forma natural de preguntarlo es `s.claim(z3.BoolVal(False))` —y es la única
formulación que no puede responder—. `check` decide `hipótesis AND afirmación`,
así que con una afirmación `False` reporta INSATISFACIBLE sean cuales sean las
hipótesis. Un usuario preguntó exactamente eso, sobre un sistema que sí tiene
modelos, y le dijeron «no existe modelo». Solo se enteró yendo a `core`.

```
$ certo check regimen.py
INSATISFACIBLE  [unsat]
  no existe modelo --pero la afirmación es el literal False, así que esto no
  dice nada de las hipótesis--. Pregúntalo con `--hypotheses-only`.
```

```
$ certo check regimen.py --hypotheses-only
SATISFACIBLE  [sat]
  el régimen NO ES VACÍO: las 3 hipótesis se sostienen a la vez, y aquí hay
  un punto donde lo hacen
  certificado: model (no necesita solver)
```

El certificado es un **modelo**, que es sin-solver: que un régimen no sea
vacío es de las pocas respuestas aquí que se re-comprueban solo evaluando. Ese
mismo usuario dijo que exhibir el conjunto completo de parámetros
simultáneamente era la primera vez en cuatro iteraciones que lo hacía en vez
de argumentarlo.

Y cuando el régimen **sí** es vacío, obtienes el choque minimal en vez del
conjunto entero de hipótesis:

```
$ certo check vacio.py --hypotheses-only
INSATISFACIBLE  [unsat]
  el régimen es VACÍO: estas hipótesis no pueden sostenerse a la vez.
  El choque minimal es: dens_floor, sparse
```

`certo lint` avisa de una afirmación constante antes de todo esto, y `prove`
reporta la vacuidad después. Esto es la misma pregunta, hecha de frente.

## Un unsat core, enunciado en Lean

`export --lean` se negaba con un `unsat_core` —el tipo que produce el comando
más usado—. Para un core sobre aritmética lineal ahora emite Lean de verdad:
ligaduras, hipótesis, el objetivo en positivo, y `sorry`.

```lean
theorem from_core (a b : ℤ)
    (a_big : 10 - a ≤ 0)
    (b_small : -3 + b ≤ 0)
    : -7 + a - b ≥ 0 := by
  sorry    -- certo: un core dice QUÉ hipótesis bastan, no por qué.
```

El tipo se lee de las fórmulas en vez de suponerse, porque un régimen entero
emitido sobre los reales elabora sin problema y dice algo más débil que lo que
se certificó. Las hipótesis que certo **descartó** van listadas al final: esa
lista es el contenido del certificado.

`sorry` y no una llamada a táctica, deliberadamente. Un core dice qué
hipótesis bastan; no dice por qué, y nada en él autoriza `linarith`. `certo
farkas` sobre el mismo spec produce los multiplicadores, y su export compila.

Un core **vacuo** es el interesante. Las hipótesis se contradicen entre sí, así
que `h₁ → … → False` es un teorema —y eso es la vacuidad del régimen,
enunciada en Lean—:

```lean
theorem regime_empty (dens : ℝ)
    (dens_floor : (3/4 : ℚ) - dens ≤ 0)
    (sparse : (-1/2 : ℚ) + dens ≤ 0)
    : False := by
  sorry
```

Fuera de la aritmética lineal lleva el SMT-LIB2 literal y lo dice. certo no
conoce tu codificación de Mathlib y no la va a adivinar.


## `lint`: antes de gastar el cómputo

Todos los demás comandos responden una pregunta. Este pregunta si la pregunta
está bien planteada, y es lo más barato de la herramienta.

```
$ certo lint examples/lint_vacuous_regime.py
Spec -- para `certo prove / check / core`
  [XX] las hipótesis se contradicen entre sí, así que cualquier demostración
       será VACUA --válida y sobre nada--. El choque es: kappa_large,
       density_high, sparse
  1 errores, 0 avisos, 0 notas
```

`certo prove` sobre ese mismo archivo también reporta la vacuidad —después de
reportar `DEMOSTRADO`, que es el momento en que alguien decide que la corrida
salió bien—. Preguntarlo antes cuesta una llamada al solver sobre un problema
estrictamente más fácil que la demostración.

Fíjate en qué hipótesis nombra. `n_large` está en el conjunto, es consistente
con todo, y no se le culpa: el choque es **minimal**, así que la siguiente
pregunta ya está respondida.

Otras tres que se pagan solas:

| Hallazgo | Por qué importa |
|---|---|
| el paso inductivo empieza después de que terminan los casos base | `induct` también se niega —después de descargar todos los casos base, que es donde se van las horas—. Aquí es comparar dos enteros. |
| el predicado devuelve `bool` | Entonces el barrido será `reproducible`, no `certificado`. Gente que escribió el predicado ella misma ha leído mal esa diferencia. |
| `integer=True` hace enteras **todas** las variables | Un usuario lo leyó como «aquí hay enteros» y obtuvo un diseño que no valía nada, con cada peso redondeado a cero. |

También cuenta el dominio sin construirlo —`items=lambda: iter(range(10**7))`
se mira por encima, nunca se materializa— y lee el tamaño de una familia de
grafos de una tabla, así que `certo lint` sobre 11 vértices responde en lo que
se tarda en leer el archivo y no en lo que tardaría el barrido.

Cargar un spec lo **ejecuta**; así funcionan los specs aquí. Más allá de eso,
lint llama al predicado como mucho una vez y nunca corre el solver sobre el
objetivo.

Códigos de salida: `0` limpio o solo notas, `1` errores, `2` avisos.

## `status`: dónde está la demostración

Veintisiete comandos y treinta tipos de certificado, y la forma de un
proyecto vivía solo en la cabeza de quien los había corrido.

```
$ certo status out/
19 certificados bajo out
  sweep 6   unsat_core 4   proof 3   farkas 2   gap 1   induction 1   sos 1

  RESULTADOS -- 9 certificados sobre los que nada más aquí se apoya
  gap            out/walkthrough.json   el núcleo canónico del recorrido
  proof          out/main.json          todo grafo 2-conexo sin K4...

  PENDIENTE -- 3 supuestos sobre los que descansan estos resultados
  main.json: density_bound
      "el argumento de conteo de la sección 3"

  HUECO -- 1 afirmaciones válidas que dicen menos de lo que aparentan
  regime.json: VACUA: las hipótesis se contradicen entre sí -- el choque es
               density_high, sparse

  DESFASADO -- 2 certificados cuyo spec se ha movido
  sweep_n7.json: el spec cambió desde que se emitió: specs/sweep7.py

  leído, no verificado. `certo status --verify` vuelve a comprobar cada uno.
```

Cuatro secciones, en el orden en que importan.

**RESULTADOS** son los certificados sobre los que nada más en el directorio se
apoya. El certificado de un lema no es un resultado; la demostración que se
sostiene sobre él, sí.

**PENDIENTE** es cada puente y cada optimalidad no afirmada, incluidos los que
están tres niveles más abajo —un puente dentro de un lema dentro de una
demostración lo sigue debiendo la demostración—. Los puentes son legítimos y a
menudo inevitables. Perderles la cuenta no lo es, y es fácil perderla
precisamente porque todo lo que los rodea verifica.

**HUECO** es lo que es válido y dice menos de lo que aparenta: una
demostración vacua con su choque nombrado, un barrido cuyo predicado nadie
certificó, un óptimo que es un valor alcanzado y no un máximo demostrado.

**DESFASADO** es un certificado cuyo spec ha cambiado desde que se emitió. No
está mal —verifica por sí solo— pero ya no describe el archivo que tiene al
lado, y seis meses después nadie recuerda cuál.

**No emite certificado**, deliberadamente. `status` no afirma nada; lee lo que
afirmaron otros comandos. Un informe que se certificara a sí mismo sería el
único artefacto aquí que nadie ha comprobado.


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

253, y sin necesidad de ningún framework de tests.

```bash
for t in smoke mcp i18n extras; do python tests/test_$t.py; done
```

Notas de versión en [CHANGELOG.md](CHANGELOG.md); lo que viene, lo bloqueado
y lo deliberadamente descartado en [BACKLOG.md](BACKLOG.md).

## Licencia

MIT. El motor de síntesis es una reimplementación del algoritmo CEGIS de
[marcelwa/CEGIS](https://github.com/marcelwa/CEGIS) (MIT), no de su código.

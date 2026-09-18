# Casos trabajados

Problemas reales, de punta a punta. Cada sección es un sitio donde la versión
obvia de un comando estaba mal y la corrección vale la pena conocerla.

[Órbitas que puedes comprobar](#órbitas-que-puedes-comprobar) ·
[Qué establece un barrido](#qué-establece-un-barrido) ·
[Simetría paramétrica](#simetría-paramétrica) ·
[De dónde salió parametric](#de-dónde-salió-parametric) ·
[Diseños mixtos](#diseños-mixtos) ·
[Cargas locales](#cargas-locales) ·
[Empaquetamientos](#empaquetamientos) ·
[Duales exactos en un vértice degenerado](#duales-exactos-en-un-vértice-degenerado)

---

## Órbitas que puedes comprobar

Una búsqueda combinatoria produce copias reetiquetadas de un objeto por
centenas. Un barrido que reporta 1400 contraejemplos donde hay cuatro
estructurales no te ha dicho cuatro cosas y las ha enterrado: te ha dicho una
cosa 1400 veces y ha dejado la lectura a tu cargo.

`canonicalize` las colapsa. Entrega una función del ítem a una forma hashable, y
un barrido que reportaba cuarenta contraejemplos reporta uno, cuarenta veces.

Eso pide que le crean. `canonicalize` es Python arbitrario, así que *"estos
cuarenta comparten forma canónica"* lo afirma el spec, y lo único que un
certificado podía comprobar era que la aritmética de la descomposición se
sostenía:

```
  [ok] las órbitas parten el dominio  (3 órbitas cubriendo 10 de 10 ítems)
  [ok] cada órbita tiene su propio representante  (0 representantes repetidos)
  [ok] cada representante pertenece a su órbita
```

Eso vale la pena tenerlo —una descomposición cuyas partes no cuadran está mal
fuera cual fuera el grupo— y ninguna de esas líneas es la pregunta.

### El otro trato

```python
labelling=lambda item: {punto_origen: etiqueta, ...}
```

Entrega la **permutación** en vez de la forma. certo la aplica, el resultado *es*
la forma canónica, y la permutación viaja en el certificado:

```
[ok] cada miembro de cada órbita lleva su permutación  (40 testigos)
[ok] cada miembro ES el representante reetiquetado, reaplicando la permutación
     guardada  (40 reaplicadas, 0 llevadas pero no decodificables, fallan: -)
AVISO: lo que los testigos muestran es que los miembros de una órbita son el
MISMO objeto reetiquetado. No muestran que dos representantes distintos sean
objetos distintos [...]
```

Declarar ambas se rechaza: una pide que le crean y la otra pide que le
comprueben.

### Por qué entregarla siquiera

La forma canónica propia de certo es exacta y **se niega** en vez de adivinar.
Sobre un objeto vértice-transitivo se niega de inmediato: una 1-factorización de
K6 tiene quince puntos que se ven todos iguales, `15!` es 1 307 674 368 000, y
conocer el grupo de automorfismos no la salva —`|Aut|` es 120, así que
cocientar por todo él aún deja 10 897 286 400 clases laterales.

Calcular bien un etiquetado canónico es una búsqueda dura que una herramienta
hecha para eso hace mucho mejor. Así que nauty encuentra el etiquetado, certo lo
comprueba, y el artefacto lleva ambos —la misma división que hace `parametric`
con su dual y `farkas` con sus multiplicadores. **Esa vía no tiene tope, porque
no se busca nada.**

Solo se descomponen los **contraejemplos**. La estructura de órbitas de todo lo
que pasó rara vez es la pregunta, y calcularla sobre un dominio grande no es
gratis.

---

## Qué establece un barrido

Un barrido que pasa y un barrido que pasa *con certificados* no son el mismo
resultado, y la brecha es ancha.

| Nivel | Qué se sostiene | Cuándo |
|---|---|---|
| **certificado** | cada evaluación lleva su propio certificado; no se confía nada en el predicado | el predicado devuelve `Outcome(ok, cert=...)` **y** `--cert-all` los guarda |
| **reproducible** | el dominio, su hash, y un vector de veredictos: repetir el predicado da las mismas respuestas | un predicado `bool` pelado — el caso común |
| **registrado** | solo el dominio y su hash | el spec no está, se movió, o nunca se selló |

```
$ certo sweep spec.py
BARRIDO FINITO REPRODUCIBLE -- el predicado NO está certificado  [unsat]
  el predicado se cumple en los 3481 ítems (DOMINIO FINITO, no el teorema)
  !! 3481 de 3481 evaluaciones no llevan certificado. El barrido es
  REPRODUCIBLE --repetir el predicado da las mismas respuestas-- pero nada aquí
  establece que esas respuestas sean correctas.
```

Las dos salvedades son independientes. "No el teorema" es sobre
**generalidad**: se comprobó un dominio finito, no todo `n`. "No certificado" es
sobre **confianza**: nada aquí dice que el predicado respondiera bien. Un
barrido que pasa solía enunciar solo la primera, y un banner verde sobre once
mil booleanos sin comprobar es donde eso hace más daño —no hay contraejemplo al
que ir a mirar.

### Repetición: el nivel intermedio, con nombre

El certificado guarda un **vector de veredictos** —un carácter por ítem, en
orden del dominio— y su digest. `verify` repite el predicado y compara:

```
$ certo verify out/sweep.json
VÁLIDO  certificado domain_sweep (reejecutando el spec, no confiando en sus respuestas)
  [ok] el hash de la familia coincide
  [ok] repetir el predicado da los mismos veredictos  (3481 evaluaciones, idénticas)
  AVISO: 3481 de 3481 evaluaciones no llevan certificado. Repetirlas concuerda,
  lo que hace el barrido reproducible; NO hace verificadas las respuestas del
  predicado.
```

Esta es la única comprobación que atrapa **un predicado editado bajo un nombre
estable**. El hash del dominio no puede —el dominio no se movió— y los
certificados guardados tampoco, porque no hay ninguno. Cuando discrepa, nombra
el ítem:

```
  [XX] repetir el predicado da los mismos veredictos
       (el ítem a=1,b=1 (índice 0) ahora responde distinto)
```

Dos consecuencias que vale la pena enunciar. La verificación cuesta ahora una
reejecución completa del predicado, que es el precio honesto de la afirmación. Y
la cabecera dice **"reejecutando el spec"** en vez de "sin solver": repetir corre
el Python del propio spec, que bien puede llamar a un solver, así que la
formulación antigua era la misma sobreafirmación un nivel más abajo.

---

## Simetría paramétrica

Un texto no simetriza un programa. Simetriza `S(p,q)` y escribe la respuesta
como fórmula en `p` y `q` —y entre las instancias que alguien corrió y la
identidad simbólica que usa la demostración hay un paso. Ese paso es
`reduce --parametric`.

Una familia se declara como órbitas cuyas multiplicidades son **polinomios**, y
filas que existen solo bajo condiciones declaradas:

```python
orbits = {"clique": C(p,2), "cross": p*q}
rows   = [("KKK", {"clique": 3},             ">=", 1, [p - 3]),
          ("KKI", {"clique": 1, "cross": 2}, ">=", 1, [p - 2, q - 1])]
```

**El objetivo no se declara.** Sustituir una variable por órbita en `Σ z_e` suma
cada órbita, así que el objetivo *son* las multiplicidades. Declararlo aparte
dejaría que ambos discreparan, y un objetivo que discrepa de los tamaños de
órbita es un error de contabilidad que ninguna cantidad de resolución atrapa.

**Una órbita está presente exactamente donde su multiplicidad es positiva** —una
medición, no una convención. La familia dividida tiene dos órbitas de aristas
para `q ≥ 1` y **una** para `q = 0`, porque no hay aristas cruzadas de las que
ser órbita.

**Los regímenes se derivan, no se listan.** Las condiciones de fila cortan el
espacio de parámetros en los programas distintos que de verdad ocurren:

```
$ certo reduce --parametric examples/parametric_symmetry.py
DEMOSTRADO  [unsat]
  el cociente simbólico coincide con la familia en los 35 puntos de la ventana:
  2 órbitas sobre parámetros (p, q), en 4 régimen(es) de las condiciones de fila
  objetos: 1/2*p^2 + p*q - 1/2*p
  regímenes: ['(ninguno)', 'KKI', 'KKK', 'KKK,KKI']
```

Una forma cerrada a trozos tiene una rama por régimen, así que una fórmula con
tres ramas sobre un programa con cuatro regímenes es una fórmula a la que le
falta un caso. El borde es donde están los errores.

### Dos niveles, mantenidos aparte

| Nivel | Qué cubre | ¿Necesita instancia? |
|---|---|---|
| simbólico | qué órbitas, qué filas, qué coeficientes, qué regímenes; que las multiplicidades dan cuenta de cada objeto | no |
| por instancia | que el grupo declarado realmente *tiene* estas órbitas con estos tamaños, y que el cociente que produce el promediado es el simbólico evaluado ahí | sí, sobre una ventana finita |

El segundo no se convierte en el primero añadiendo puntos, y `verify` lo repite
cada vez. Lo que compra la ventana es **falsabilidad**: quita una condición
—lleva `3x ≥ 1` a `p = 2`, donde no hay triángulos sobre tres vértices de
clique— y queda refutado en 7 de los 35 puntos, el primero `p=2, q=0`. Una
multiplicidad de `pq/2` en vez de `pq` falla en 30; `p²/2` en vez de `C(p,2)` en
los 35.

No dice nada sobre el **valor**. Resuelve el cociente con `opt` en un punto, o
acótalo para todo parámetro con `parametric`, que es el comando hecho para ese
traspaso.

---

## De dónde salió parametric

Una instancia real, y la estructura vale la pena verla. Un LP simetrizado
resuelto exactamente para `p = 5..12` con un símplex racional escrito a mano dio
duales que son **constantes a trozos con umbrales** —un vértice en `p = 6`, otro
a lo largo de `p = 7, 8, 9`, un tercero desde `p = 10`. En cada trozo la cota es
un polinomio en `p` y el dual es fijo, que es exactamente la forma que
`certo parametric` certifica. Los umbrales son parte de la respuesta, no algo
que suavizar.

### La forma recubrimiento vino de la otra dirección

Tres textos separados del mismo argumento, cada uno reduciéndose a un programa
de recubrimiento simetrizado sobre dos, tres o cuatro órbitas de aristas, cada
uno enunciando el valor como mínimo de formas cerradas con nombre, y cada uno
terminando con *"la dualidad completa la demostración"*.

Con **qué** la completa la dualidad es un dual por rama y una comprobación de
que cada uno sigue factible a lo largo de su rama —un objeto finito que nadie
había escrito, y exactamente un certificado.

```
$ certo parametric examples/parametric_cover.py
DEMOSTRADO  [unsat]
  para todo p >= 3, s >= 0, el óptimo es al menos 1/2*p^2 - 1/2*p
  sentido: min
```

Dos cosas cambian con un recubrimiento, y ambas son forzadas y no elegidas.

**El dual no es una constante.** En un empaquetamiento los multiplicadores son
tasas, un racional cada uno. El dual de un recubrimiento es él mismo un
empaquetamiento, y un empaquetamiento de un objeto que crece crece con él
—`C(p,2)` triángulos, no `1/3`. Así que una entrada del dual puede ser un
polinomio, y `y ≥ 0` se vuelve el mismo test de desplazamiento que cualquier
otra fila.

**Un umbral en la función de valor es la factibilidad del dual.** El ejemplo
certifica la rama `q ≥ p − 1` de una forma cerrada que cambia de forma en
`q = p − 1`. Su única fila no trivial es

```
p q - 2 C(p,2)  =  p (q - p + 1)  =  p s   >=  0
```

que es no negativa exactamente en esa rama. El dual deja de ser factible
precisamente donde la forma cerrada cambia de rama —que es lo que *es* un
umbral en una función de valor lineal a trozos, visto desde abajo. Cada rama es
su propio spec y su propio certificado, porque cada una es su propia afirmación.

`examples/parametric_orbits.py` es lo mismo un tamaño más arriba: cuatro órbitas
de aristas, cinco tipos de triángulo, tres recubrimientos candidatos, y las
condiciones de rama cayendo del dual como una fila residual y una no
negatividad.

---

## Diseños mixtos

Un MILP que elige una estructura discreta *y* un empaquetamiento fraccionario
compatible al mismo tiempo es una forma que `opt` no podía expresar en absoluto:
`LPSpec(integer=True)` hace enteras **todas** las variables, que es otro
problema, no una restricción de este. Las variables llevan un tipo en su lugar:

```python
lp.variable("y17", kind="binary")     # reserva este triángulo
lp.variable("q42")                    # empaqueta fraccionariamente en lo que queda
```

Para una **demostración de existencia**, que la elección discreta fuera óptima
no importa —exhibir una construcción que alcanza el objetivo es todo el trabajo.
Así que el flujo deliberadamente no es "certificar el MILP":

```
búsqueda (CBC, heurística)  →  congela la parte discreta
                            →  LP residual sobre la parte continua
                            →  dual exacto, todo exacto
                            →  compara contra el objetivo
```

```
$ certo mixed examples/mixed_design.py --target 10
SATISFACIBLE  [sat]
  diseño certificado alcanzando 28/3, objetivo 10
  alcanzado 28/3 = 6 discreto + 10/3 continuo | cota de relajación 28/3
  el valor alcanzado iguala la cota de relajación, así que ESTE es el óptimo global
```

### La comprobación que lo hace más que tres archivos en una carpeta

```
$ certo verify out/mixed.json
  [ok] el punto completo satisface cada restricción original
  [ok] el propio certificado del LP residual se sostiene
  [ok] y ese residual ES el problema original con esta asignación sustituida
```

Sin esa última, el subcertificado podría ser sobre un problema *distinto* —la
misma brecha que `compose` cierra entre un lema y el enunciado para el que se
usa.

La respuesta de CBC es una **conjetura hasta que algo la comprueba**: devuelve
`0.9999997` para una binaria tan a menudo como no, así que la asignación se
redondea y luego se verifica contra las restricciones originales en aritmética
exacta. Un diseño que no sobrevive esa comprobación se rechaza en vez de
reportarse.

### Quedarse corto no es un certificado inválido

Un diseño que no llega a su objetivo verifica como **VÁLIDO** con un aviso. El
certificado es correcto; el diseño es insuficiente, y son afirmaciones
distintas. Leer `INVÁLIDO` ahí diría que algo está roto cuando no lo está.

La optimalidad MILP completa —un certificado de ramificación y acotación con un
dual exacto o una prueba de infactibilidad en cada hoja— es
`certo mixed --prove-optimal`, y es algo distinto y mucho mayor que lo que una
demostración de existencia necesita.

---

## Cargas locales

Un certificado de empaquetamiento demuestra un óptimo. Lo que un argumento suele
necesitar después es distinto: **y el diseño respeta las cotas que puse en cada
región, por este margen, y esa me costó esto.**

```python
PackingSpec(
    items=..., capacities=1,
    loads=[("within_A", {"p0": 1, "p1": 1, "p2": 1}, "<=", 2),
           ("within_B", {"p3": 1, "p4": 1, "p5": 1}, "<=", 5)],
)
```

```
$ certo opt examples/packing_with_loads.py
  óptimo EXACTO certificado: 5 (denominador <= 1)
  2 cargas declaradas, y lo que el diseño les hace:
    within_A         2 <= 2   AJUSTADA
                     cuesta 1 por unidad de cota -- relajarla compra eso
    within_B         3 <= 5   holgura 2
```

Lee la segunda columna. `within_A` está **ajustada** y su precio sombra es 1:
relaja esa cota en uno y el óptimo sube exactamente uno. `within_B` tiene holgura
2, así que no es lo que te está frenando y apretar el argumento ahí no compra
nada. Esa es la diferencia entre una cota que trabaja y una que va de paseo —y
es gratis, porque una carga es una fila y el dual ya la tarificó.

Una capacidad es parte de la **codificación**; una carga es parte del
**argumento**. Se declaran por separado por eso, y se reportan aparte.

`verify` recalcula cada valor alcanzado desde el primal en vez de creerse el
declarado, así que un certificado que subestima lo que una región usó falla:

```
[XX] la carga `within_A` se cumple, y en el valor declarado   2 <= 2, holgura 0
```

Las cargas aceptan `<=`, `>=` o `==`. La última es preservación exacta —*esta
región lleva exactamente esto*— que es lo que significa "preservar estas cargas
locales" cuando el argumento depende del valor y no de un techo.

Se rechazan en vez de aceptarse en silencio: un peso sobre un ítem que no está
en el empaquetamiento, y un nombre de carga que choca con un recurso.

---

## Empaquetamientos

Cliques compitiendo por aristas, bloques compitiendo por puntos —la forma se
repite, y reconstruir el LP a mano cada vez es donde se esconden los errores.

```python
from certo import PackingSpec
from certo.graphs import Graph

def spec():
    g = Graph.from_edges(6, [...])
    return PackingSpec.cliques_in_graph(g, gains={3: 2, 4: 5})
```

`to_lp()` devuelve un `LPSpec`, así que los racionales exactos y el dual
verificable vienen gratis. **El dual es el certificado de carga**: los nombres
de restricción son nombres de recurso, así que `y_r` se lee como "la carga sobre
el recurso r" —normalmente el objeto que de verdad querías.

```
$ certo opt examples/packing_mixed.py --by-type
  mixto      25/2       óptimo EXACTO certificado: 25/2
  K3         10         óptimo EXACTO certificado: 10
  K4         25/2       óptimo EXACTO certificado: 25/2
```

Si mezclar compra algo es la brecha entre el óptimo mixto y el mejor tipo
único. Aquí, sobre K6, no compra nada sobre K4 puro.

`PackingSpec(integer={"K3"})` pone los ítems estructurales enteros mientras el
resto queda como relajación fraccionaria, que es la forma común. Sobre tal
problema `opt` reporta **solo la cota de relajación** y lo dice: redondear cada
variable convertiría un peso K4 de 1/6 en cero y reportaría un diseño que no
vale nada. El valor alcanzable sale de congelar la parte discreta y resolver el
resto, que es [`certo mixed`](#diseños-mixtos).

---

## Duales exactos en un vértice degenerado

`opt` reconstruye un primal y un dual racionales desde un solver flotante y los
comprueba exactamente. Hay un régimen donde eso no puede funcionar: un óptimo
**degenerado**, donde muchas soluciones duales son óptimas y la que CBC devuelve
no tiene por qué redondear sobre ninguna de ellas.

Un usuario certificó 56 LP exactamente y **3 necesitaron el primal y el dual
racionales inyectados a mano** —todos ellos sobre soluciones simétricas. Eso no
es mala suerte. La simetría produce degeneración, CBC devuelve un dual óptimo
arbitrario, y redondear *ese en particular* puede no ser dual-factible en
absoluto.

El arreglo no es una escalera de denominadores más larga. Dado un primal exacto,
la holgura complementaria determina el dual: `yᵢ = 0` en cada fila con holgura, y
`Σᵢ Aᵢⱼ yᵢ = cⱼ` para cada `j` con `xⱼ > 0`. Eso es un sistema lineal sobre las
filas ajustadas, resuelto en `Fraction` sin flotantes en ninguna parte. Donde
indetermina el dual —más filas ajustadas que variables activas, que es
exactamente lo que produce la simetría— la libertad sobrante **es** el conjunto
de duales óptimos, así que cada elección se ofrece por turno.

```
max 2x + 3y   s.a.  x + y ≤ 1,  x + 2y ≤ 1,  x, y ≥ 0
```

Ambas filas están ajustadas en el óptimo y solo una variable está activa.
Certificarlo funciona **sin ningún dual usable del solver**:

| lo que devolvió CBC | certificado | dual usado |
|---|---|---|
| nada (`0, 0`) | sí | `(0, 2)` |
| disparates (`7.3, -2.1`) | sí | `(0, 2)` |
| el dual de otro vértice | sí | `(0, 1.5)` → `(0, 2)` |

Un dual derivado **no** se cree por haber sido derivado. Es un candidato, como
uno redondeado, y se gana el certificado pasando el mismo `check_lp` exacto. Lo
que cambió es de dónde vienen los candidatos: la estructura del problema en vez
de donde sea que aterrizó un solver flotante.

Pasado un puñado de filas ajustadas, enumerar bases es inviable —sobre un
recubrimiento exacto realista con 98 filas, 49 de ellas ajustadas y 7 variables
activas, eso son C(49, 7) candidatos, unos 10⁸. Así que a partir de ahí certo
resuelve el dual directamente con un **símplex de dos fases en racionales
exactos**: regla de Bland en todo momento, que es más lenta que la de arista más
pronunciada y no puede ciclar. En un mecanismo de reserva que solo corre cuando
la vía barata ya falló, terminar importa más que ser rápido.

Nada de lo que produce se cree por haberse producido ahí. El resultado pasa por
el mismo `check_lp` que una conjetura redondeada, así que un fallo ahí aparece
como certificado que no verifica —nunca como uno equivocado que sí.

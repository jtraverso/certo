"""CNF con variables por nombre, DIMACS, y codificaciones de apoyo.

Las variables se piden por nombre y el objeto lleva la traduccion a enteros
DIMACS. Asi el certificado puede volver a imprimir un modelo legible sin la
sesion de Python que lo produjo.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class CNF:
    def __init__(self, title: str = ""):
        self.title = title
        self._id: dict = {}          # nombre -> entero positivo
        self._name: list = [None]    # entero -> nombre (1-indexado)
        self.clauses: list = []
        self._aux = 0

    # -- variables ---------------------------------------------------------

    def var(self, name) -> int:
        name = str(name)
        v = self._id.get(name)
        if v is None:
            v = len(self._name)
            self._id[name] = v
            self._name.append(name)
        return v

    def aux(self, tag="aux") -> int:
        self._aux += 1
        return self.var("__{}_{}".format(tag, self._aux))

    def name_of(self, v: int) -> str:
        return self._name[abs(v)]

    @property
    def nvars(self) -> int:
        return len(self._name) - 1

    # -- clausulas ---------------------------------------------------------

    def add(self, *lits) -> "CNF":
        """Anade una clausula. Normaliza: quita repetidos, descarta tautologias."""
        flat: list = []
        for x in lits:
            flat.extend(x) if isinstance(x, (list, tuple)) else flat.append(x)
        seen = set()
        cl = []
        for l in flat:
            if l == 0:
                raise ValueError("0 no es un literal valido")
            if -l in seen:
                return self  # tautologia: no aporta nada
            if l not in seen:
                seen.add(l)
                cl.append(int(l))
        self.clauses.append(cl)
        return self

    def add_all(self, clauses) -> "CNF":
        for c in clauses:
            self.add(*c)
        return self

    # -- codificaciones ----------------------------------------------------

    def at_least_one(self, lits) -> "CNF":
        return self.add(*lits)

    def at_most_one(self, lits) -> "CNF":
        """Pairwise. Cuadratica, pero exacta y sin variables auxiliares."""
        lits = list(lits)
        for i in range(len(lits)):
            for j in range(i + 1, len(lits)):
                self.add(-lits[i], -lits[j])
        return self

    def exactly_one(self, lits) -> "CNF":
        lits = list(lits)
        return self.at_least_one(lits).at_most_one(lits)

    def implies(self, a, b) -> "CNF":
        return self.add(-a, b)

    def lex_leq(self, xs, ys) -> "CNF":
        """Fuerza (x_1..x_k) <=lex (y_1..y_k). La base para romper simetrias."""
        xs, ys = list(xs), list(ys)
        if len(xs) != len(ys):
            raise ValueError("lex_leq necesita dos vectores de la misma longitud")
        eq = self.aux("lexeq")
        self.add(eq)  # e_0 = verdadero
        for i, (x, y) in enumerate(zip(xs, ys)):
            # e_i -> (x_i <= y_i)
            self.add(-eq, -x, y)
            if i == len(xs) - 1:
                break
            nxt = self.aux("lexeq")
            # nxt <-> eq AND (x_i <-> y_i)
            self.add(-nxt, eq)
            self.add(-nxt, -x, y)
            self.add(-nxt, x, -y)
            self.add(nxt, -eq, x, y)
            self.add(nxt, -eq, -x, -y)
            eq = nxt
        return self

    def break_vertex_symmetry(self, edge_var, n, mode="transpositions") -> "CNF":
        """Rompe simetrias de vertices sobre variables de arista.

        `edge_var(i, j)` devuelve el literal de la arista {i,j}. Con
        transposiciones adyacentes el corte es parcial pero barato: es lo
        estandar cuando el grupo completo es demasiado grande.
        """
        pairs = [(i, j) for j in range(n) for i in range(j)]
        if mode != "transpositions":
            raise ValueError("modo no soportado: " + mode)
        for t in range(n - 1):
            perm = list(range(n))
            perm[t], perm[t + 1] = perm[t + 1], perm[t]
            xs = [edge_var(i, j) for i, j in pairs]
            ys = [edge_var(*sorted((perm[i], perm[j]))) for i, j in pairs]
            self.lex_leq(xs, ys)
        return self

    # -- DIMACS ------------------------------------------------------------

    def to_dimacs(self) -> str:
        out = []
        if self.title:
            out.append("c " + self.title.replace("\n", " "))
        for v in range(1, len(self._name)):
            out.append("c var {} {}".format(v, self._name[v]))
        out.append("p cnf {} {}".format(self.nvars, len(self.clauses)))
        for cl in self.clauses:
            out.append(" ".join(map(str, cl)) + " 0")
        return "\n".join(out) + "\n"

    @classmethod
    def from_dimacs(cls, text: str) -> "CNF":
        c = cls()
        names: dict = {}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("c var "):
                parts = line.split(None, 3)
                if len(parts) == 4:
                    names[int(parts[2])] = parts[3]
                continue
            if line.startswith("c"):
                if not c.title:
                    c.title = line[1:].strip()
                continue
            if line.startswith("p"):
                nv = int(line.split()[2])
                for v in range(1, nv + 1):
                    c.var(names.get(v, "x{}".format(v)))
                continue
            lits = [int(t) for t in line.split()]
            if lits and lits[-1] == 0:
                lits.pop()
            if lits:
                for l in lits:
                    while c.nvars < abs(l):
                        c.var("x{}".format(c.nvars + 1))
                c.add(*lits)
        return c

    def decode(self, true_vars) -> dict:
        """{nombre: bool} legible, saltando las auxiliares."""
        t = set(true_vars)
        return {
            self._name[v]: (v in t)
            for v in range(1, len(self._name))
            if not self._name[v].startswith("__")
        }


@dataclass
class CNFSpec:
    """Lo que devuelve spec() para `cases`."""

    cnf: CNF
    title: str = ""
    expect: str = ""  # 'unsat' o 'sat', opcional: solo documenta la intencion
    meta: dict = field(default_factory=dict)

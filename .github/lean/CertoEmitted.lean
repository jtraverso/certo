-- Placeholder. CI overwrites Emitted.lean with what `certo export --lean`
-- produces and compiles it, so the claim "this output compiles" is checked
-- rather than asserted. Pinned to the Mathlib revision the exporters were
-- developed against; a newer one may need the imports adjusting, which is
-- exactly what this job is for.
import Mathlib.Data.Real.Basic

example : (1 : ℝ) + 1 = 2 := by norm_num

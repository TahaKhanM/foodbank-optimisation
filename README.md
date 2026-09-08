# Food-bank parcel optimisation

A mixed-integer optimisation model for choosing affordable food parcels subject to nutrient, stock and variety constraints. The interesting part is translating a parcel into integer package quantities: calorie ratios remain linear, while category coverage needs binary variables. PuLP formulates the model and CBC searches for the least-cost feasible combination.

This began as a collaborative study of allocation at the Trussell Trust Woking food bank. The [original paper](Final_copy-3.pdf) is by **Shiv Barua, Koby Reiss Din, Taha Khan and Jack Wickham**, listed alphabetically. It reports a £26.52 observed parcel and a £12.03 optimised nine-day comparison. **The original `fb.xlsx` food catalogue is absent, so those results cannot be independently reproduced from this repository.** They are historical paper results, not results of the demonstration below. The paper and Git history do not establish each author's exact share of the code or fieldwork.

The current implementation makes the optimisation inspectable and runnable with an explicitly synthetic catalogue. It accepts stock limits, exclusions and configurable parcel-wide bounds, checks inputs before solving and returns quantities only after checking an optimal integer solution against the constraints.

## Run the model

Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python foodbank.py
python foodbank.py --exclude 'Fruit D'
python -m pytest -q
```

The default run uses [synthetic foods](examples/synthetic-foods.csv) and an [illustrative policy](examples/synthetic-policy.json). Every nutrient and price in that catalogue is invented for software testing. These are not products, shopping advice or dietary recommendations. The committed [result](examples/synthetic-result.json) records its optimal cost and nutrient totals. CBC ships with the tested PuLP distribution; an unavailable solver produces an explicit error.

Supply a CSV or Excel workbook with your own per-package data:

```bash
python foodbank.py --catalogue foods.xlsx --policy parcel-policy.json --output parcel.json
```

Excel uses the first sheet. Required columns are `Item`, `Price (£)`, `Calories (kcal)`, `Fat (g)`, `Saturates (g)`, `Carbohydrate (g)`, `Sugars (g)`, `Fibre (g)`, `Protein (g)` and `Salt (g)`. Optional columns are `Stock` (whole packages), `Category` (one category per item) and `Portions` (a user-defined portion count per package). All quantities must refer to the **same package unit**. Prices must be positive; nutrient and stock values must be finite and nonnegative. Names are trimmed but package sizes are preserved, avoiding the original risk of merging distinct products.

Policy bounds are totals for the **whole parcel**; the code does not infer daily needs from a recipient's body measurements. For example, `"Protein (g)": [70, null]` sets a lower bound of 70 g, with no upper bound. `energy_fractions` converts gram totals to energy before constraining their share of total calories. Unknown fields, malformed bounds and misspelled exclusions fail explicitly.

## Formulation and decisions

For package counts $x_i \in \mathbb{Z}_{\geq 0}$, unit cost $c_i$ and nutrient content $a_{ki}$, the objective is $\min \sum_i c_i x_i$, subject to supplied nutrient bounds and optional stock limits. Whole packages avoid fractional tins; this makes it a MILP rather than a simplex-only LP.

A fat-energy interval $[l,u]$ becomes $lC \leq 9\sum_i a_{\mathrm{fat},i}x_i \leq uC$, where $C$ is total calories. These constraints are linear because each side is a linear expression in the package counts. The optional calorie-concentration cap similarly limits each item's share of total calories.

For every nonempty category, a binary witness $y_c$ satisfies $y_c \leq \sum_{i\in c}x_i$. Requiring $\sum_c y_c \geq k$ forces at least $k$ represented categories. A reverse big-M constraint is unnecessary: the variables witness coverage and are not reported as a complete classification of selected categories. This keeps the formulation smaller and avoids an arbitrary M. Category counts and total portions are independent constraints; neither demonstrates daily variety or compliance with a nutritional guideline.

`build_model` separates formulation from `solve_parcel`, so a reviewer can inspect the PuLP constraints or supply another solver through the Python API. Solver variable names use row indices rather than sanitised food names, preventing names such as `a-b` and `a b` from colliding. Infeasibility returns `quantities: null` and a nonzero CLI exit status; it is never presented as a zero-cost parcel.

## What is verified

Tests compare the solver objective with an **independent exhaustive enumeration** of a small bounded catalogue. They also check the demonstration's nutrient ratios, category and portion coverage, stock limits, exclusions, infeasibility, malformed input and solver-name collisions. CI runs these checks and the example from a clean checkout.

The 2026 revision replaces the original import-time script, unused `likes`/`dislikes` arguments, global DataFrame mutation and duplicated totals with explicit inputs and a testable solver boundary. [The original script](historical/original_foodbank.py) is retained unchanged for comparison with the paper; it still requires the missing spreadsheet. The historical hardcoded fish, salt, saturated-fat and “5-a-day” proxies have not been silently repackaged as validated nutrition policy.

## Scope and remaining work

The solver establishes optimality **within the supplied model**. It does not establish that the policy is nutritionally appropriate, affordable in a current shop or operationally feasible for a food bank. The original report and code also disagree on some bounds, including protein and saturated fat; recovering the catalogue and reconciling those definitions is necessary before replicating the paper.

There is no meal schedule, micronutrient model, spoilage, preparation cost, uncertainty analysis or allergy ontology. An exclusion is an exact product-name filter and cannot establish allergen safety. Positive prices guarantee a bounded cost objective but do not represent donated stock's opportunity cost. Actual deployment would need verified product units, an agreed nutrition policy, inventory integration and expert review of the resulting parcels. An LP relaxation would be useful as a lower-cost bound; it would not produce the same package-feasible decision.

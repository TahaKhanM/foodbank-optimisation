# Food-bank parcel optimisation

A mixed-integer model that chooses the cheapest whole-package food parcel meeting supplied nutrient, stock and variety constraints. PuLP builds the model and CBC solves it. Tests compare the objective against exhaustive enumeration on a small catalogue.

The implementation supports CSV or Excel input, product exclusions, stock caps and parcel-wide bounds. It checks an optimal integer solution against the constraints before returning quantities. An infeasible model returns an explicit failure.

The project began as a collaborative study at the Trussell Trust Woking food bank. The [paper](Final_copy-3.pdf) is by **Shiv Barua, Koby Reiss Din, Taha Khan and Jack Wickham**. Its historical £26.52 observed parcel and £12.03 optimised comparison depend on a missing source catalogue. The runnable example below uses synthetic data and does not reproduce those results.

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

The later implementation separates input validation, model construction and solving. [The original script](historical/original_foodbank.py) remains available for comparison with the paper and requires the missing spreadsheet.

## Limits

The result is optimal for the supplied model. Real use needs verified package data and an agreed nutrition policy. The synthetic example is for software testing and does not provide dietary advice.

The model has no meal schedule, micronutrient coverage, spoilage or preparation costs. Product-name exclusions are exact filters and do not establish allergen safety. Reproducing the original study also requires recovering `fb.xlsx` and reconciling the paper's nutrient bounds with the historical script.

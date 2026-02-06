# Food Bank Parcel Optimisation with Linear Programming

This repository accompanies the preprint **“A detailed study of Food Bank’s resource allocation and optimisation of nutrition using linear programming”** (included as `Final_copy-3.pdf`).

## Project summary

Food banks are essential for addressing food insecurity, but standardised allocation forms can miss two practical constraints:

1. **Nutrition**: parcels can be calorie-sufficient while still being imbalanced (e.g., high sugar/salt, low variety).
2. **Operations**: allocation can be *recipe-like* rather than *inventory- and recipient-aware*.

We collected primary observations of the Trussell Trust Woking food bank’s allocation process, used those to estimate an **average parcel**, and then built an optimisation model that chooses quantities of available items to produce a parcel that is **(i) nutritionally constrained** and **(ii) cost-minimising**, while allowing personalisation via recipient details.

The included `foodbank.py` constructs and solves this optimisation model using **PuLP**.

## Mathematical theory

### 1) Linear (and integer) programming formulation

Let there be $n$ food items.

- Decision variables: $x_i \in \mathbb{Z}_{\ge 0}$, the number of units of item $i$ included in the parcel.
- Cost: $c_i$ (price per unit).
- Nutrients: $a_{k,i}$, amount of nutrient $k$ per unit of item $i$.

A basic cost-minimising model is:
$$
\begin{aligned}
\min_{x \in \mathbb{Z}_{\ge 0}^n} \quad & \sum_{i=1}^n c_i x_i \\
\text{s.t.} \quad & L_k \le \sum_{i=1}^n a_{k,i} x_i \le U_k, \quad \forall k \\
\quad & x_i \in \mathbb{Z}_{\ge 0}.
\end{aligned}
$$
This project extends that template in two main ways:

- Some constraints are **ratio constraints** (e.g., fat calories as a fraction of total calories). These can be written as linear inequalities by moving terms to one side.
- Some constraints involve **variety/coverage** (e.g., “5-a-day” across categories). This is naturally modelled with additional **binary** variables and linking constraints.

Because we use integer and binary decision variables, the implemented model is a **mixed-integer linear program (MILP)**, not a pure LP.

### 2) Nutritional constraints used

Below is the conceptual structure implemented in `foodbank.py`:

#### Calories via Harris–Benedict BEE

For weight $w$ (kg), height $h$ (cm), age $a$ (years), and parcel length $d$ (days), the minimum calorie requirement is built from the Harris–Benedict basal energy expenditure (BEE):
$$
\text{BEE}_\text{male} = 66.5 + 13.8w + 5h - 6.8a
$$
$$
\text{BEE}_\text{female} = 655.1 + 9.6w + 1.9h - 4.7a
$$
Then:
$$
C_{\min} = d \cdot \text{BEE}, \qquad
C_{\max} = \alpha \cdot C_{\min}
$$
where $\alpha$ is set to 1.2 (no frequent rigorous exercise) or 1.5 (frequent rigorous exercise).

#### Macronutrient ratio constraints

Let total calories be $\text{Cal} = \sum_i \text{cal}_i x_i$.

- Fat: fats contribute $9$ kcal per gram, so
$$
  0.20\,\text{Cal} \le 9\sum_i \text{fat}_i x_i \le 0.35\,\text{Cal}.
$$
- Carbohydrates: carbs contribute $4$ kcal per gram, so
$$
  0.45\,\text{Cal} \le 4\sum_i \text{carb}_i x_i \le 0.65\,\text{Cal}.
$$
- Sugar cap:
$$
  4\sum_i \text{sugar}_i x_i \le 0.10\,\text{Cal}.
$$
#### Minimums / ranges

- Protein minimum scales with body mass and days (implemented as $0.8\,w\,d$ grams).
- Fibre minimum scales with days.
- Salt range scales with days.
- Additional constraints enforce minimum fish intake and a “5-a-day” style fruit/veg requirement.

> Note: the preprint describes certain guideline constraints at a high level; the code translates these into explicit numeric bounds (e.g., gram/day bounds and portion conversions). See `foodbank.py` for the exact implemented constants.

### 3) 5-a-day and variety via binary variables

Variety requirements are difficult to express using only $x$-variables, because “at least one item from category” is a logical condition.

Introduce binary variables $y_c \in \{0,1\}$ for categories $c$ (e.g., veg, fruit, pulses). Link them to item choices:
$$
 y_c \le \sum_{i \in \mathcal{I}(c)} x_i \quad \forall c
$$
and require:
$$
\sum_c y_c \ge 5
$$
alongside a separate constraint ensuring total portions across eligible items is at least $5d$.

## Simplex (and what’s happening under the hood)

### LP geometry and simplex

If we ignore integrality and treat $x_i \ge 0$ as continuous, we obtain an LP:
$$
\min\; c^\top x \;\;\text{s.t.}\; Ax \le b,\; x\ge 0.
$$
Geometrically, the feasible region is a convex polytope. The **simplex method** exploits the fact that an LP optimum (if it exists) occurs at a **vertex** (a *basic feasible solution*). Simplex moves from vertex to adjacent vertex by pivoting the basis, improving the objective until no improving adjacent move exists.

### Why MILP matters

This project uses **integer** food quantities and **binary** category indicators, so the solver is tackling a MILP. Standard MILP solvers typically use:

- **Branch-and-bound / branch-and-cut** to enforce integrality.
- **LP relaxations** at nodes (often solved by simplex or interior-point methods).

So “simplex” still plays a role: it is often used repeatedly to solve the LP relaxations that guide the integer search.

## Repository contents

- `Final_copy-3.pdf` — the preprint describing data collection, constraints, and results.
- `foodbank.py` — the optimisation model implementation (PuLP + pandas).

## How to run

### 1) Install dependencies

```bash
pip install pulp pandas openpyxl
```

### 2) Provide the food database

`foodbank.py` expects an Excel file named `fb.xlsx` in the repository root with a sheet called `Sheet1` and columns:

- `Item`
- `Calories (kcal)`
- `Fat (g)`
- `Saturates (g)`
- `Carbohydrate (g)`
- `Sugars (g)`
- `Fibre (g)`
- `Protein (g)`
- `Salt (g)`
- `Price (£)`

### 3) Run

```bash
python foodbank.py
```

At the bottom of the script there is an example call for an “average” UK male profile and a comparison against the observed average parcel.

## Results highlight (from the paper)

Using observed parcel composition as a baseline, the preprint reports that optimised parcels can be **~53–55% cheaper** while meeting nutritional constraints, e.g. the median-male 9-day parcel comparison shows the optimised parcel cost dropping from ~£26.52 to ~£12.03 alongside improvements such as lower sugars and saturates and higher fibre.

See Tables/Figures in `Final_copy-3.pdf` for the full comparisons.

## What we learned building this project

### Mathematical / modelling

- Turning real-world public health guidance into a constraint system requires **unit discipline** (grams vs kcal, per-day vs per-parcel, portions vs unit sizes).
- Some “obvious” requirements are naturally **logical** (variety, category coverage). Modelling these cleanly pushed us beyond basic LP into **MILP** with binary variables.
- Small modelling choices can change feasibility dramatically; diagnosing infeasibility is often about finding which constraint set is too tight.

### Technical

- **Linear programming in Python**: building models using PuLP and reasoning about how constraints translate into solver behaviour.
- **(Practical) simplex**: even when using a library solver, we learned how simplex relates to LP relaxations and why integer problems need additional machinery.
- **Data handling**: structuring a clean “food database” (pandas DataFrame), standardising item naming, and keeping the code path reproducible.
- **Validation**: comparing the optimised output to a baseline parcel quantitatively (percentage deviation tables).

## Limitations and future work

- Integrating **inventory constraints** explicitly (per-branch stock limits) would make the model more operationally realistic.
- Extending dietary constraints to include **micronutrients** (iron, vitamin C, etc.) would improve health coverage.
- Packaging this as a simple web app/API could streamline real-world adoption.

## Citation
The preprint can be found at: https://www.researchgate.net/publication/384667932_A_detailed_study_of_Food_Bank's_resource_allocation_and_optimisation_of_nutrition_using_linear_programming


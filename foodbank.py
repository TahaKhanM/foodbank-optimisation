"""Cost-minimising integer food parcels with explicit, auditable constraints."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd
import pulp

NUTRIENTS = ['Calories (kcal)', 'Fat (g)', 'Saturates (g)', 'Carbohydrate (g)',
             'Sugars (g)', 'Fibre (g)', 'Protein (g)', 'Salt (g)']


def validate_catalogue(frame):
    required = ['Item', 'Price (£)', *NUTRIENTS]
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f'missing catalogue columns: {sorted(missing)}')
    if frame.empty:
        raise ValueError('catalogue must contain at least one item')
    frame = frame.copy().reset_index(drop=True)
    if frame['Item'].isna().any():
        raise ValueError('item names cannot be missing')
    frame['Item'] = frame['Item'].astype(str).str.strip()
    if frame['Item'].eq('').any() or frame['Item'].str.casefold().duplicated().any():
        raise ValueError('item names must be nonempty and unique (ignoring case)')
    for column in ['Price (£)', *NUTRIENTS, *[c for c in ['Stock', 'Portions'] if c in frame]]:
        frame[column] = pd.to_numeric(frame[column], errors='raise')
        if not all(math.isfinite(v) and v >= 0 for v in frame[column]):
            raise ValueError(f'{column}: values must be finite and nonnegative')
    if (frame['Price (£)'] <= 0).any():
        raise ValueError('prices must be positive to keep the cost model well bounded')
    if 'Stock' in frame and (frame['Stock'] % 1 != 0).any():
        raise ValueError('stock must be whole units')
    if 'Category' in frame:
        frame['Category'] = frame['Category'].fillna('').astype(str).str.strip()
    return frame


def bounds(value, label, fraction=False):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f'{label}: expected [minimum, maximum], using null for an open bound')
    lo, hi = value
    for number in value:
        if number is not None and (not isinstance(number, (int, float)) or not math.isfinite(number) or number < 0 or (fraction and number > 1)):
            raise ValueError(f'{label}: invalid bound')
    if lo is not None and hi is not None and lo > hi:
        raise ValueError(f'{label}: minimum exceeds maximum')
    return lo, hi


def build_model(frame, policy, exclude=()):
    frame = validate_catalogue(frame)
    if not isinstance(policy, dict) or any(not isinstance(policy.get(key, {}), dict) for key in ['nutrients', 'energy_fractions']):
        raise ValueError('policy and nutrient bounds must be JSON objects')
    allowed = {'nutrients', 'energy_fractions', 'max_item_calorie_fraction', 'min_categories', 'min_portions'}
    unknown = set(policy) - allowed
    if unknown:
        raise ValueError(f'unknown policy fields: {sorted(unknown)}')
    excluded = {name.strip().casefold() for name in exclude}
    if excluded - set(frame['Item'].str.casefold()):
        raise ValueError('excluded item not found in catalogue')
    problem = pulp.LpProblem('Food_Parcel', pulp.LpMinimize)
    variables = [pulp.LpVariable(f'item_{i}', lowBound=0, cat='Integer') for i in frame.index]
    for i, row in frame.iterrows():
        if row['Item'].casefold() in excluded:
            variables[i].upBound = 0
        elif 'Stock' in frame:
            variables[i].upBound = float(row['Stock'])
    totals = {column: pulp.lpSum(float(frame.loc[i, column]) * variables[i] for i in frame.index)
              for column in ['Price (£)', *NUTRIENTS]}
    problem += totals['Price (£)']

    def constrain(expression, pair, name, reference=1, fraction=False):
        lo, hi = bounds(pair, name, fraction)
        if lo is not None:
            problem.addConstraint(expression >= lo * reference, name=f'{name}_min')
        if hi is not None:
            problem.addConstraint(expression <= hi * reference, name=f'{name}_max')

    for index, (nutrient, pair) in enumerate(policy.get('nutrients', {}).items()):
        if nutrient not in NUTRIENTS:
            raise ValueError(f'unknown nutrient: {nutrient}')
        constrain(totals[nutrient], pair, f'nutrient_{index}')
    factors = {'Fat (g)': 9, 'Saturates (g)': 9, 'Carbohydrate (g)': 4, 'Sugars (g)': 4, 'Protein (g)': 4}
    for index, (nutrient, pair) in enumerate(policy.get('energy_fractions', {}).items()):
        if nutrient not in factors:
            raise ValueError(f'no energy conversion for {nutrient}')
        constrain(factors[nutrient] * totals[nutrient], pair, f'energy_{index}', totals['Calories (kcal)'], True)
    if 'max_item_calorie_fraction' in policy:
        cap = policy['max_item_calorie_fraction']
        bounds([None, cap], 'max_item_calorie_fraction', True)
        if cap is None or cap == 0:
            raise ValueError('max_item_calorie_fraction must be in (0, 1]')
        for i in frame.index:
            problem += float(frame.loc[i, 'Calories (kcal)']) * variables[i] <= cap * totals['Calories (kcal)'], f'concentration_{i}'
    if 'min_categories' in policy:
        minimum = policy['min_categories']
        if not isinstance(minimum, int) or minimum < 0 or 'Category' not in frame:
            raise ValueError('min_categories requires a nonnegative integer and a Category column')
        indicators = []
        for index, category in enumerate(sorted(set(frame['Category']) - {''})):
            indicator = pulp.LpVariable(f'category_{index}', cat='Binary')
            indices = frame.index[frame['Category'] == category]
            problem += indicator <= pulp.lpSum(variables[i] for i in indices), f'category_present_{index}'
            indicators.append(indicator)
        problem += pulp.lpSum(indicators) >= minimum, 'category_count'
    if 'min_portions' in policy:
        minimum = policy['min_portions']
        bounds([minimum, None], 'min_portions')
        if minimum is None or 'Portions' not in frame:
            raise ValueError('min_portions requires a numeric minimum and a Portions column')
        problem += pulp.lpSum(float(frame.loc[i, 'Portions']) * variables[i] for i in frame.index) >= minimum, 'portions'
    return problem, variables, frame


def solve_parcel(frame, policy, exclude=(), solver=None):
    problem, variables, frame = build_model(frame, policy, exclude)
    problem.solve(solver or pulp.PULP_CBC_CMD(msg=False))
    status = pulp.LpStatus[problem.status]
    if status != 'Optimal' or problem.sol_status != pulp.LpSolutionOptimal:
        return {'status': status, 'quantities': None, 'totals': None}
    quantities = [int(round(variable.value())) for variable in variables]
    for variable, quantity in zip(variables, quantities):
        if abs(variable.value() - quantity) > 1e-5:
            raise RuntimeError('solver returned a non-integer quantity')
        variable.varValue = quantity
    # Recheck the rounded solution; never publish an infeasible parcel as a result.
    if not problem.valid(1e-5):
        raise RuntimeError('solver solution failed constraint validation')
    return {'status': status,
            'quantities': {frame.loc[i, 'Item']: q for i, q in enumerate(quantities) if q},
            'totals': {c: sum(float(frame.loc[i, c]) * q for i, q in enumerate(quantities)) for c in ['Price (£)', *NUTRIENTS]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    examples = Path(__file__).parent / 'examples'
    parser.add_argument('--catalogue', type=Path, default=examples / 'synthetic-foods.csv')
    parser.add_argument('--policy', type=Path, default=examples / 'synthetic-policy.json')
    parser.add_argument('--exclude', action='append', default=[], help='exact item name; may be repeated')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        frame = pd.read_excel(args.catalogue) if args.catalogue.suffix.lower() == '.xlsx' else pd.read_csv(args.catalogue)
        result = solve_parcel(frame, json.loads(args.policy.read_text()), args.exclude)
    except (ValueError, OSError, pulp.PulpSolverError) as error:
        parser.exit(2, f'error: {error}\n')
    output = json.dumps(result, indent=2) + '\n'
    print(output, end='')
    if args.output:
        args.output.write_text(output)
    return 0 if result['status'] == 'Optimal' else 1


if __name__ == '__main__':
    raise SystemExit(main())

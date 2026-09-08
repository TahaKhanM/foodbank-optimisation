from itertools import product
from pathlib import Path
import json
import pandas as pd
import pytest
from foodbank import build_model, solve_parcel, validate_catalogue

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


def catalogue():
    return pd.read_csv(EXAMPLES / 'synthetic-foods.csv')


def test_optimum_matches_independent_exhaustive_search():
    frame = catalogue().iloc[:3].copy()
    frame['Stock'] = 3
    policy = {'nutrients': {'Calories (kcal)': [1000, 1200], 'Protein (g)': [40, None]}, 'min_categories': 2}
    feasible = []
    for q in product(range(4), repeat=3):
        calories = sum(frame.iloc[i]['Calories (kcal)'] * n for i, n in enumerate(q))
        protein = sum(frame.iloc[i]['Protein (g)'] * n for i, n in enumerate(q))
        if 1000 <= calories <= 1200 and protein >= 40 and sum(n > 0 for n in q) >= 2:
            feasible.append(sum(frame.iloc[i]['Price (£)'] * n for i, n in enumerate(q)))
    result = solve_parcel(frame, policy)
    assert result['status'] == 'Optimal'
    assert result['totals']['Price (£)'] == pytest.approx(min(feasible))


def test_demo_constraints_inventory_and_preferences():
    frame = catalogue()
    policy = json.loads((EXAMPLES / 'synthetic-policy.json').read_text())
    result = solve_parcel(frame, policy, exclude=['Fruit D'])
    assert result['status'] == 'Optimal'
    assert 'Fruit D' not in result['quantities']
    t = result['totals']
    assert 1800 <= t['Calories (kcal)'] <= 2200
    assert .15 <= 9 * t['Fat (g)'] / t['Calories (kcal)'] <= .35
    assert t['Protein (g)'] >= 70 and t['Fibre (g)'] >= 30 and t['Salt (g)'] <= 6
    chosen = frame.set_index('Item').loc[list(result['quantities'])]
    assert chosen.Category.nunique() >= 3
    assert sum(chosen.loc[item, 'Portions'] * q for item, q in result['quantities'].items()) >= 5
    for item, q in result['quantities'].items():
        assert q <= chosen.loc[item, 'Stock']
        assert chosen.loc[item, 'Calories (kcal)'] * q <= .5 * t['Calories (kcal)']


def test_infeasible_has_no_fake_zero_parcel():
    frame = catalogue()
    frame['Stock'] = 0
    result = solve_parcel(frame, {'nutrients': {'Calories (kcal)': [1, None]}})
    assert result == {'status': 'Infeasible', 'quantities': None, 'totals': None}


@pytest.mark.parametrize('column,value', [('Item', 'Grain A'), ('Price (£)', -1), ('Salt (g)', float('nan')), ('Stock', .5)])
def test_reject_invalid_catalogue(column, value):
    frame = catalogue()
    frame[column] = frame[column].astype(object)
    frame.loc[1, column] = value
    with pytest.raises(ValueError):
        validate_catalogue(frame)


def test_duplicate_solver_names_cannot_merge_items():
    frame = catalogue().iloc[:2].copy()
    frame['Item'] = ['a-b', 'a b']
    problem, variables, _ = build_model(frame, {})
    assert len(set(v.name for v in variables)) == 2


def test_reject_unknown_exclusion_and_invalid_policy():
    for policy, exclude in [({}, ['typo']), ({'nutrients': {'Calories (kcal)': [2, 1]}}, []), ({'max_item_calorie_fraction': 2}, []), ({'stock': 2}, [])]:
        with pytest.raises(ValueError):
            build_model(catalogue(), policy, exclude)

import numpy as np
import sys
import numpy as np
import sys
import pulp
import pandas as pd
import os

# Correct the file path to point to the correct Excel file in the same directory
file_path = 'fb.xlsx'

# Load the Excel file into a DataFrame
xls = pd.ExcelFile(file_path)

# Load the data from the first sheet into a DataFrame
df_full = pd.read_excel(xls, sheet_name='Sheet1')

# Strip any leading/trailing whitespace in the "Item" column
df_full["Item"] = df_full["Item"].str.strip()

# Extract data and save it in a DataFrame
data = {
    "Item": df_full["Item"].tolist(),
    "Calories (kcal)": df_full["Calories (kcal)"].tolist(),
    "Fat (g)": df_full["Fat (g)"].tolist(),
    "Saturates (g)": df_full["Saturates (g)"].tolist(),
    "Carbohydrate (g)": df_full["Carbohydrate (g)"].tolist(),
    "Sugars (g)": df_full["Sugars (g)"].tolist(),
    "Fibre (g)": df_full["Fibre (g)"].tolist(),
    "Protein (g)": df_full["Protein (g)"].tolist(),
    "Salt (g)": df_full["Salt (g)"].tolist(),
    "Price (£)": df_full["Price (£)"].tolist()
}

# Create the DataFrame with the same structure
df = pd.DataFrame(data)

# Average Parcel Values
avg_parcel = {
    'Calories': 17230,
    'Fat': 402,
    'Saturates': 178,
    'Carbohydrates': 2596,
    'Sugars': 920,
    'Fibre': 284,
    'Protein': 622,
    'Salt': 41,
    'Price': 26.52
}


def calculate_deviation(parcel1, parcel2):
    deviations = {}
    for key in parcel1:
        parcel1_value = parcel1[key]
        parcel2_value = parcel2[key]
        deviation = (parcel1_value - parcel2_value) / parcel2_value * 100
        deviations[key] = deviation
    return deviations


def compare_parcel_to_average(variable_parcel):
    # Calculate the percentage deviation between the variable parcel and the average parcel
    deviations = calculate_deviation(variable_parcel, avg_parcel)

    print("Comparison of Variable Parcel to Average Parcel:\n")
    for key in avg_parcel:
        deviation = deviations[key]
        print(f"{key}:")
        print(f"  Average Parcel Value: {avg_parcel[key]}")
        print(f"  Variable Parcel Value: {variable_parcel[key]}")
        print(f"  Deviation: {deviation:.2f}%\n")

    return deviations


def print_dict_with_spacing(input_dict):
    for key, value in input_dict.items():
        print(f"{key}: {value}")
        print("-" * 20)


def simplex_algorithm(weight, exercise, height, age, likes, dislikes, gender, day):
    # Clean the food item names by making them lowercase and removing weights
    df["Item"] = df["Item"].str.lower().str.replace(r'\d+g|\d+ml', '', regex=True).str.strip()

    # Create the problem variable
    prob = pulp.LpProblem("Food_Parcel_Optimization", pulp.LpMinimize)

    # Decision variables for the amount of each food item in the food parcel
    food_vars = {item: pulp.LpVariable(f"Food_{item}", lowBound=0, cat="Integer") for item in df["Item"]}

    # Objective function: minimize total cost (original price calculation)
    prob += pulp.lpSum([df.loc[i, "Price (£)"] * food_vars[df.loc[i, "Item"]] for i in df.index])

    # Nutritional constraints
    total_calories = pulp.lpSum([df.loc[i, "Calories (kcal)"] * food_vars[df.loc[i, "Item"]] for i in df.index])

    if gender == 'M':
        calorie_min = day * (66.5 + 13.8 * weight + 5 * height - 6.8 * age)
    elif gender == 'F':
        calorie_min = day * (655.1 + 9.6 * weight + 1.9 * height - 4.7 * age)
    else:
        calorie_min = day * (66.5 + 13.8 * weight + 5 * height - 6.8 * age)

    if exercise:
        calorie_max = 1.5 * calorie_min
    else:
        calorie_max = 1.2 * calorie_min

    prob += total_calories >= calorie_min
    prob += total_calories <= calorie_max

    total_fat = pulp.lpSum([df.loc[i, "Fat (g)"] * food_vars[df.loc[i, "Item"]] for i in df.index])
    calories_from_fat = total_fat * 9
    prob += calories_from_fat >= 0.20 * total_calories
    prob += calories_from_fat <= 0.35 * total_calories

    total_saturates = pulp.lpSum([df.loc[i, "Saturates (g)"] * food_vars[df.loc[i, "Item"]] for i in df.index])
    prob += total_saturates <= 30 * day
    prob += total_saturates >= 13 * day

    total_carbs = pulp.lpSum([df.loc[i, "Carbohydrate (g)"] * food_vars[df.loc[i, "Item"]] for i in df.index])
    prob += total_carbs >= 0.45 * total_calories / 4
    prob += total_carbs <= 0.65 * total_calories / 4

    total_sugar_calories = pulp.lpSum([df.loc[i, "Sugars (g)"] * 4 * food_vars[df.loc[i, "Item"]] for i in df.index])
    prob += total_sugar_calories <= 0.10 * total_calories

    total_fibre = pulp.lpSum([df.loc[i, "Fibre (g)"] * food_vars[df.loc[i, "Item"]] for i in df.index])
    prob += total_fibre >= 30 * day

    total_protein = pulp.lpSum([df.loc[i, "Protein (g)"] * food_vars[df.loc[i, "Item"]] for i in df.index])
    protein_min = 0.8 * weight * day
    prob += total_protein >= protein_min

    total_salt = pulp.lpSum([df.loc[i, "Salt (g)"] * food_vars[df.loc[i, "Item"]] for i in df.index])
    prob += total_salt <= 6 * day
    prob += total_salt >= 1.3 * day

    # Define fish constraints
    fish_items = ["tinned fish"]
    fish_weight_per_tin = 120
    desired_fish_weight = 40 * day
    total_fish_weight = pulp.lpSum([food_vars.get(fish, 0) * fish_weight_per_tin for fish in fish_items])
    prob += total_fish_weight >= desired_fish_weight

    # 5-a-Day categories and items
    portion_sizes = {
        "squash": 150, "tinned vegetables": 80, "tinned fruit can": 80, "tinned tomatoes": 80,
        "beans": 80, "lentils": 80, "pulses": 80, "chickpeas": 80, "raisins": 30,
        "soup": 80, "pasta sauce": 80, "potatoes: mashed": 80, "potatoes: tinned": 80
    }

    unit_weights = {
        "squash": 1000, "tinned vegetables": 300, "tinned fruit can": 300, "tinned tomatoes": 400,
        "beans": 420, "lentils": 500, "pulses": 500, "chickpeas": 400, "raisins": 500,
        "soup": 400, "pasta sauce": 500, "potatoes: mashed": 425, "potatoes: tinned": 345
    }

    five_a_day_items = [
        "tinned tomatoes", "pasta sauce", "soup", "tinned vegetables", "potatoes: mashed",
        "potatoes: tinned", "raisins", "squash", "beans", "lentils", "pulses", "chickpeas",
        "tinned fruit can"
    ]

    category_map = {
        "tomato": ["tinned tomatoes", "pasta sauce", "soup"],
        "veg": ["tinned vegetables"],
        "potato": ["potatoes: mashed", "potatoes: tinned"],
        "dried_fruit": ["raisins"],
        "juice": ["squash"],
        "beans_pulses": ["beans", "lentils", "pulses", "chickpeas"],
        "fruit": ["tinned fruit can"]
    }

    # Binary variables for categories
    category_vars = {category: pulp.LpVariable(f"Category_{category}", 0, 1, cat="Binary") for category in category_map}

    total_five_a_day_portions = pulp.lpSum([
        food_vars.get(item, 0) * unit_weights[item] / portion_sizes[item] for item in five_a_day_items
    ])
    prob += total_five_a_day_portions >= 5 * day

    for category, items in category_map.items():
        prob += category_vars[category] <= pulp.lpSum([food_vars.get(item, 0) for item in items])

    prob += pulp.lpSum([category_vars[cat] for cat in category_vars]) >= 5

    if "pasta" in df["Item"].values and "pasta sauce" in df["Item"].values:
        prob += food_vars["pasta sauce"] <= food_vars["pasta"]

    for i in df.index:
        item = df.loc[i, "Item"]
        prob += (df.loc[i, "Calories (kcal)"] * food_vars[item]) <= 0.20 * total_calories

    # Solve the problem
    prob.solve()

    variable_parcel = {
        'Calories': 0,
        'Fat': 0,
        'Saturates': 0,
        'Carbohydrates': 0,
        'Sugars': 0,
        'Fibre': 0,
        'Protein': 0,
        'Salt': 0,
        'Price': 0
    }

    if pulp.LpStatus[prob.status] == 'Optimal':
        for i in df.index:
            item = df.loc[i, "Item"]
            qty = food_vars[item].varValue if item in food_vars else 0
            if qty and qty > 0:
                variable_parcel['Calories'] += df.loc[i, "Calories (kcal)"] * qty
                variable_parcel['Fat'] += df.loc[i, "Fat (g)"] * qty
                variable_parcel['Saturates'] += df.loc[i, "Saturates (g)"] * qty
                variable_parcel['Carbohydrates'] += df.loc[i, "Carbohydrate (g)"] * qty
                variable_parcel['Sugars'] += df.loc[i, "Sugars (g)"] * qty
                variable_parcel['Fibre'] += df.loc[i, "Fibre (g)"] * qty
                variable_parcel['Protein'] += df.loc[i, "Protein (g)"] * qty
                variable_parcel['Salt'] += df.loc[i, "Salt (g)"] * qty
                variable_parcel['Price'] += df.loc[i, "Price (£)"] * qty
    else:
        print("No optimal solution found.")

    total_nutrients = {nutrient: 0 for nutrient in ['Calories (kcal)', 'Fat (g)', 'Saturates (g)', 'Carbohydrate (g)', 'Sugars (g)', 'Fibre (g)', 'Protein (g)', 'Salt (g)']}

    print("\nStatus:", pulp.LpStatus[prob.status])

    if pulp.LpStatus[prob.status] == 'Optimal':
        for i in df.index:
            item = df.loc[i, "Item"]
            qty = food_vars[item].varValue if item in food_vars else 0
            if qty and qty > 0:
                print(f"{item}:  {qty:.2f} units ")
    else:
        print("No optimal solution found.")

    print("\n")

    print_dict_with_spacing(variable_parcel)

    return variable_parcel, prob, food_vars, total_nutrients


# Running for an average male in the UK
variable_parcel, prob, food_vars, total_nutrients = simplex_algorithm(84.5, False, 177.9, 40.7, likes=[], dislikes=[], gender='M', day=9)
# Run comparison
compare_parcel_to_average(variable_parcel)
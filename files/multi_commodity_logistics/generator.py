# generator.py
import os
import pandas as pd

def generate_data():
    """
    Generates the CSV data files for the multi-commodity logistics optimization problem.
    The data is specifically designed to result in a known optimal solution cost.
    """
    task_folder = 'multi_commodity_logistics'
    if not os.path.exists(task_folder):
        os.makedirs(task_folder)

    # 1. warehouses.csv
    warehouses_data = {
        'warehouse_id': ['W1', 'W2', 'W3'],
        'annual_cost': [40000, 35000, 50000],
        'capacity_standard': [4000, 5000, 10000],
        'capacity_refrigerated': [3000, 2000, 10000]
    }
    warehouses_df = pd.DataFrame(warehouses_data)
    warehouses_df.to_csv(os.path.join(task_folder, 'warehouses.csv'), index=False)

    # 2. factories.csv
    factories_data = {
        'factory_id': ['F1', 'F2'],
        'production_cost_standard': [25, 30],
        'production_cost_perishable': [35, 33],
        'production_capacity': [13000, 10000]
    }
    factories_df = pd.DataFrame(factories_data)
    factories_df.to_csv(os.path.join(task_folder, 'factories.csv'), index=False)

    # 3. customer_demand.csv
    customer_demand_data = {
        'customer_id': ['C1', 'C1', 'C2', 'C2'],
        'product_type': ['Standard', 'Perishable', 'Standard', 'Perishable'],
        'demand_units': [5000, 3000, 4000, 2000]
    }
    customer_demand_df = pd.DataFrame(customer_demand_data)
    customer_demand_df.to_csv(os.path.join(task_folder, 'customer_demand.csv'), index=False)

    # 4. transport_costs.csv
    # Costs are carefully chosen to guide the optimal solution.
    # High costs (999) make certain routes infeasible in practice.
    transport_costs_data = {
        'origin': ['F1', 'F1', 'F1', 'F2', 'F2', 'W1', 'W2',
                   'F2', 'F1', 'W1', 'W2', 'F2'],
        'destination': ['C1', 'W1', 'W2', 'W2', 'C2', 'C1', 'C2',
                        'W1', 'C2', 'C2', 'C1', 'C1'],
        'cost_per_unit': [15.005, 13.5, 11.1, 10.1, 999, 10, 9.25,
                          999, 999, 999, 999, 999]
    }
    transport_costs_df = pd.DataFrame(transport_costs_data)
    transport_costs_df.to_csv(os.path.join(task_folder, 'transport_costs.csv'), index=False)

    # 5. handling_costs.csv
    handling_costs_data = {
        'location_id': ['F1', 'F2', 'W1', 'W2', 'W3'],
        'cost_per_unit': [6, 6, 10, 10, 10]
    }
    handling_costs_df = pd.DataFrame(handling_costs_data)
    handling_costs_df.to_csv(os.path.join(task_folder, 'handling_costs.csv'), index=False)
    
    print(f"Data generated in '{task_folder}' directory.")

if __name__ == "__main__":
    generate_data()
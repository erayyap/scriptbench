# solver.py
import pandas as pd
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpBinary, value

def solve_logistics_problem():
    """
    Solves the multi-commodity logistics optimization problem
    based on data from the '/multi_commodity_logistics' directory.
    """
    # --- 1. Load Data ---
    folder = 'multi_commodity_logistics'
    try:
        warehouses_df = pd.read_csv(f'{folder}/warehouses.csv')
        factories_df = pd.read_csv(f'{folder}/factories.csv')
        demand_df = pd.read_csv(f'{folder}/customer_demand.csv')
        transport_df = pd.read_csv(f'{folder}/transport_costs.csv')
        handling_df = pd.read_csv(f'{folder}/handling_costs.csv')
    except FileNotFoundError as e:
        print(f"Error: {e}. Please run generator.py first.")
        return

    # --- 2. Define Sets and Parameters ---
    PRODUCTS = demand_df['product_type'].unique().tolist()
    FACTORIES = factories_df['factory_id'].tolist()
    WAREHOUSES = warehouses_df['warehouse_id'].tolist()
    CUSTOMERS = demand_df['customer_id'].unique().tolist()
    NODES = FACTORIES + WAREHOUSES + CUSTOMERS
    HANDLING_LOCATIONS = FACTORIES + WAREHOUSES
    
    # Parameters
    demand = demand_df.set_index(['customer_id', 'product_type'])['demand_units'].to_dict()
    prod_cost_std = factories_df.set_index('factory_id')['production_cost_standard'].to_dict()
    prod_cost_per = factories_df.set_index('factory_id')['production_cost_perishable'].to_dict()
    prod_cap = factories_df.set_index('factory_id')['production_capacity'].to_dict()
    wh_fixed_cost = warehouses_df.set_index('warehouse_id')['annual_cost'].to_dict()
    wh_cap_std = warehouses_df.set_index('warehouse_id')['capacity_standard'].to_dict()
    wh_cap_ref = warehouses_df.set_index('warehouse_id')['capacity_refrigerated'].to_dict()
    handling_cost = handling_df.set_index('location_id')['cost_per_unit'].to_dict()
    transport_cost = transport_df.set_index(['origin', 'destination'])['cost_per_unit'].to_dict()

    # --- 3. Initialize Model ---
    model = LpProblem("Multi_Commodity_Logistics", LpMinimize)

    # --- 4. Define Decision Variables ---
    # Flow variables: x[origin, destination, product]
    flow = LpVariable.dicts("Flow", 
                            ((o, d, p) for o in FACTORIES + WAREHOUSES for d in WAREHOUSES + CUSTOMERS for p in PRODUCTS), 
                            lowBound=0, cat='Continuous')
    
    # Warehouse open/closed state: y[warehouse]
    wh_open = LpVariable.dicts("WarehouseOpen", WAREHOUSES, cat=LpBinary)

    # Synergy discount state for W1
    w1_synergy_active = LpVariable("W1SynergyActive", cat=LpBinary)
    
    # **FIX**: New variable to represent the linearized discount amount
    synergy_discount_amount = LpVariable("SynergyDiscountAmount", lowBound=0, cat='Continuous')

    # --- 5. Define Objective Function ---
    # a. Fixed warehouse costs
    fixed_cost = lpSum(wh_open[w] * wh_fixed_cost[w] for w in WAREHOUSES)

    # b. Production costs
    prod_cost_total = lpSum(
        lpSum(flow[f, d, 'Standard'] for d in WAREHOUSES + CUSTOMERS) * prod_cost_std[f] +
        lpSum(flow[f, d, 'Perishable'] for d in WAREHOUSES + CUSTOMERS) * prod_cost_per[f]
        for f in FACTORIES
    )

    # c. Handling costs
    handling_cost_total = lpSum(
        flow[loc, d, p] * handling_cost[loc]
        for loc in HANDLING_LOCATIONS for d in WAREHOUSES + CUSTOMERS for p in PRODUCTS
    )

    # d. Transportation costs
    transport_cost_total = lpSum(
        flow[o, d, 'Standard'] * transport_cost.get((o, d), 99999) +
        flow[o, d, 'Perishable'] * transport_cost.get((o, d), 99999) * 1.2
        for o in FACTORIES + WAREHOUSES for d in WAREHOUSES + CUSTOMERS
    )

    # **FIX**: The objective now subtracts the new linearized variable
    model += fixed_cost + prod_cost_total + handling_cost_total + transport_cost_total - synergy_discount_amount, "Total_Cost"

    # --- 6. Define Constraints ---
    # 1. Demand Fulfillment
    for c in CUSTOMERS:
        for p in PRODUCTS:
            model += lpSum(flow[o, c, p] for o in FACTORIES + WAREHOUSES) == demand.get((c, p), 0), f"Demand_{c}_{p}"

    # 2. Capacity Limits
    # Factory production capacity
    for f in FACTORIES:
        model += lpSum(flow[f, d, p] for d in WAREHOUSES + CUSTOMERS for p in PRODUCTS) <= prod_cap[f], f"FactoryCap_{f}"
    
    # Warehouse capacity
    M = 999999 # A large number for enforcing binary logic
    for w in WAREHOUSES:
        total_in_std = lpSum(flow[o, w, 'Standard'] for o in FACTORIES)
        total_in_per = lpSum(flow[o, w, 'Perishable'] for o in FACTORIES)
        model += total_in_std <= wh_cap_std[w] + wh_cap_ref[w] * wh_open[w], f"WHCap_Std_{w}"
        model += total_in_per <= wh_cap_ref[w] * wh_open[w], f"WHCap_Ref_{w}"
        # Also ensure flow only happens if warehouse is open
        model += lpSum(flow[w, d, p] for d in CUSTOMERS for p in PRODUCTS) <= M * wh_open[w], f"FlowOut_If_Open_{w}"

    # 3. Flow Conservation
    for w in WAREHOUSES:
        for p in PRODUCTS:
            model += lpSum(flow[o, w, p] for o in FACTORIES) >= lpSum(flow[w, d, p] for d in CUSTOMERS), f"FlowCons_{w}_{p}"

    # 4. Strategic Sourcing Mandate
    total_perishable_demand = sum(d for (c, p), d in demand.items() if p == 'Perishable')
    for f in FACTORIES:
        model += lpSum(flow[f, d, 'Perishable'] for d in WAREHOUSES + CUSTOMERS) <= 0.60 * total_perishable_demand, f"Sourcing_{f}"

    # 5. Direct-to-Customer SLA for C1
    total_c1_demand = sum(d for (c, p), d in demand.items() if c == 'C1')
    model += lpSum(flow[f, 'C1', p] for f in FACTORIES for p in PRODUCTS) >= 0.25 * total_c1_demand, "SLA_C1"

    # 6. Capital Expenditure Budget
    model += lpSum(wh_open[w] * wh_fixed_cost[w] for w in WAREHOUSES) <= 75000, "Budget"

    # 7. Supplier Synergy Discount for W1
    # Conditions for the synergy to be *possible*
    model += w1_synergy_active <= wh_open['W1'], "SynergyImpliesOpen"
    model += lpSum(flow['F2', 'W1', p] for p in PRODUCTS) <= M * (1 - w1_synergy_active), "SynergyExclusivity"

    # **FIX**: Linearization constraints for the discount amount
    # This variable represents the potential discount if synergy is active.
    potential_discount = lpSum(
        (flow['W1', c, 'Standard'] * transport_cost.get(('W1', c), 99999) +
         flow['W1', c, 'Perishable'] * transport_cost.get(('W1', c), 99999) * 1.2) * 0.1
        for c in CUSTOMERS
    )
    M_discount = 100000 # A sufficiently large number for the discount value
    # If synergy is not active (w1_synergy_active=0), discount must be 0
    model += synergy_discount_amount <= M_discount * w1_synergy_active, "Discount_If_Active"
    # The discount cannot be more than its calculated potential value
    model += synergy_discount_amount <= potential_discount, "Discount_Upper_Bound"
    # If synergy is active (w1_synergy_active=1), forces the discount to be at least its potential value
    model += synergy_discount_amount >= potential_discount - M_discount * (1 - w1_synergy_active), "Discount_Lower_Bound"


    # --- 7. Solve the Model ---
    model.solve()
    
    # --- 8. Print the Result ---
    if model.status == 1: # 1 means Optimal
        final_cost = round(value(model.objective))
        print(f"ANSWER={final_cost}")
    else:
        print("Optimal solution not found.")
        print("Model status:", model.status)

if __name__ == "__main__":
    solve_logistics_problem()
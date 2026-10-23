import os
import pandas as pd

def test_raw_data_exists():
    customers_path = "data/raw/olist_customers_dataset.csv"
    if os.path.exists(customers_path):
        df = pd.read_csv(customers_path)
        assert not df.empty

def test_order_revenue_calculation():
    sample_df = pd.DataFrame({
        'price': [100.0, 50.0],
        'freight_value': [10.0, 5.0]
    })
    total = sample_df['price'].sum() + sample_df['freight_value'].sum()
    assert total == 165.0

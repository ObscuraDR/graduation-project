"""
Generate Synthetic Training Data
Creates synthetic network traffic data mimicking CICIDS2017 structure
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_synthetic_data(n_samples=10000):
    """Generate synthetic network traffic data"""
    logger.info(f"Generating {n_samples} synthetic samples...")
    
    # Feature names from features.json
    feature_names = [
        "flow_duration", "total_fwd_packets", "total_backward_packets",
        "total_length_of_fwd_packets", "total_length_of_bwd_packets",
        "fwd_packet_length_max", "fwd_packet_length_min", "fwd_packet_length_mean",
        "bwd_packet_length_max", "bwd_packet_length_min", "bwd_packet_length_mean",
        "flow_bytes_per_sec", "flow_packets_per_sec", "flow_iat_mean",
        "flow_iat_std", "flow_iat_max", "flow_iat_min",
        "fwd_iat_total", "bwd_iat_total", "fwd_psh_flags", "bwd_psh_flags"
    ]
    
    # Generate normal traffic (80%)
    n_normal = int(n_samples * 0.8)
    normal_data = {
        "flow_duration": np.random.exponential(1.0, n_normal),
        "total_fwd_packets": np.random.poisson(50, n_normal),
        "total_backward_packets": np.random.poisson(40, n_normal),
        "total_length_of_fwd_packets": np.random.exponential(5000, n_normal),
        "total_length_of_bwd_packets": np.random.exponential(4000, n_normal),
        "fwd_packet_length_max": np.random.uniform(100, 1500, n_normal),
        "fwd_packet_length_min": np.random.uniform(20, 100, n_normal),
        "fwd_packet_length_mean": np.random.uniform(100, 800, n_normal),
        "bwd_packet_length_max": np.random.uniform(100, 1500, n_normal),
        "bwd_packet_length_min": np.random.uniform(20, 100, n_normal),
        "bwd_packet_length_mean": np.random.uniform(100, 800, n_normal),
        "flow_bytes_per_sec": np.random.uniform(1000, 100000, n_normal),
        "flow_packets_per_sec": np.random.uniform(10, 1000, n_normal),
        "flow_iat_mean": np.random.exponential(0.01, n_normal),
        "flow_iat_std": np.random.exponential(0.005, n_normal),
        "flow_iat_max": np.random.exponential(0.1, n_normal),
        "flow_iat_min": np.random.uniform(0.001, 0.01, n_normal),
        "fwd_iat_total": np.random.exponential(0.5, n_normal),
        "bwd_iat_total": np.random.exponential(0.4, n_normal),
        "fwd_psh_flags": np.random.poisson(5, n_normal),
        "bwd_psh_flags": np.random.poisson(3, n_normal),
        "Label": ["Normal"] * n_normal
    }
    
    # Generate DDoS traffic (10%)
    n_ddos = int(n_samples * 0.1)
    ddos_data = {
        "flow_duration": np.random.exponential(5.0, n_ddos),
        "total_fwd_packets": np.random.poisson(500, n_ddos),
        "total_backward_packets": np.random.poisson(100, n_ddos),
        "total_length_of_fwd_packets": np.random.exponential(50000, n_ddos),
        "total_length_of_bwd_packets": np.random.exponential(10000, n_ddos),
        "fwd_packet_length_max": np.random.uniform(100, 1500, n_ddos),
        "fwd_packet_length_min": np.random.uniform(20, 100, n_ddos),
        "fwd_packet_length_mean": np.random.uniform(100, 800, n_ddos),
        "bwd_packet_length_max": np.random.uniform(100, 1500, n_ddos),
        "bwd_packet_length_min": np.random.uniform(20, 100, n_ddos),
        "bwd_packet_length_mean": np.random.uniform(100, 800, n_ddos),
        "flow_bytes_per_sec": np.random.uniform(100000, 1000000, n_ddos),
        "flow_packets_per_sec": np.random.uniform(1000, 10000, n_ddos),
        "flow_iat_mean": np.random.exponential(0.001, n_ddos),
        "flow_iat_std": np.random.exponential(0.0005, n_ddos),
        "flow_iat_max": np.random.exponential(0.01, n_ddos),
        "flow_iat_min": np.random.uniform(0.0001, 0.001, n_ddos),
        "fwd_iat_total": np.random.exponential(0.1, n_ddos),
        "bwd_iat_total": np.random.exponential(0.05, n_ddos),
        "fwd_psh_flags": np.random.poisson(50, n_ddos),
        "bwd_psh_flags": np.random.poisson(10, n_ddos),
        "Label": ["DDoS"] * n_ddos
    }
    
    # Generate PortScan traffic (5%)
    n_portscan = int(n_samples * 0.05)
    portscan_data = {
        "flow_duration": np.random.exponential(0.5, n_portscan),
        "total_fwd_packets": np.random.poisson(10, n_portscan),
        "total_backward_packets": np.random.poisson(2, n_portscan),
        "total_length_of_fwd_packets": np.random.exponential(1000, n_portscan),
        "total_length_of_bwd_packets": np.random.exponential(200, n_portscan),
        "fwd_packet_length_max": np.random.uniform(100, 1500, n_portscan),
        "fwd_packet_length_min": np.random.uniform(20, 100, n_portscan),
        "fwd_packet_length_mean": np.random.uniform(100, 800, n_portscan),
        "bwd_packet_length_max": np.random.uniform(100, 1500, n_portscan),
        "bwd_packet_length_min": np.random.uniform(20, 100, n_portscan),
        "bwd_packet_length_mean": np.random.uniform(100, 800, n_portscan),
        "flow_bytes_per_sec": np.random.uniform(2000, 20000, n_portscan),
        "flow_packets_per_sec": np.random.uniform(20, 200, n_portscan),
        "flow_iat_mean": np.random.exponential(0.05, n_portscan),
        "flow_iat_std": np.random.exponential(0.02, n_portscan),
        "flow_iat_max": np.random.exponential(0.5, n_portscan),
        "flow_iat_min": np.random.uniform(0.005, 0.05, n_portscan),
        "fwd_iat_total": np.random.exponential(0.2, n_portscan),
        "bwd_iat_total": np.random.exponential(0.1, n_portscan),
        "fwd_psh_flags": np.random.poisson(2, n_portscan),
        "bwd_psh_flags": np.random.poisson(1, n_portscan),
        "Label": ["PortScan"] * n_portscan
    }
    
    # Generate Botnet traffic (5%)
    n_botnet = int(n_samples * 0.05)
    botnet_data = {
        "flow_duration": np.random.exponential(2.0, n_botnet),
        "total_fwd_packets": np.random.poisson(100, n_botnet),
        "total_backward_packets": np.random.poisson(80, n_botnet),
        "total_length_of_fwd_packets": np.random.exponential(10000, n_botnet),
        "total_length_of_bwd_packets": np.random.exponential(8000, n_botnet),
        "fwd_packet_length_max": np.random.uniform(100, 1500, n_botnet),
        "fwd_packet_length_min": np.random.uniform(20, 100, n_botnet),
        "fwd_packet_length_mean": np.random.uniform(100, 800, n_botnet),
        "bwd_packet_length_max": np.random.uniform(100, 1500, n_botnet),
        "bwd_packet_length_min": np.random.uniform(20, 100, n_botnet),
        "bwd_packet_length_mean": np.random.uniform(100, 800, n_botnet),
        "flow_bytes_per_sec": np.random.uniform(5000, 50000, n_botnet),
        "flow_packets_per_sec": np.random.uniform(50, 500, n_botnet),
        "flow_iat_mean": np.random.exponential(0.02, n_botnet),
        "flow_iat_std": np.random.exponential(0.01, n_botnet),
        "flow_iat_max": np.random.exponential(0.2, n_botnet),
        "flow_iat_min": np.random.uniform(0.002, 0.02, n_botnet),
        "fwd_iat_total": np.random.exponential(0.3, n_botnet),
        "bwd_iat_total": np.random.exponential(0.25, n_botnet),
        "fwd_psh_flags": np.random.poisson(10, n_botnet),
        "bwd_psh_flags": np.random.poisson(8, n_botnet),
        "Label": ["Botnet"] * n_botnet
    }
    
    # Combine all data
    all_data = {}
    for key in normal_data.keys():
        all_data[key] = list(normal_data[key]) + list(ddos_data[key]) + list(portscan_data[key]) + list(botnet_data[key])
    
    df = pd.DataFrame(all_data)
    
    # Shuffle
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    logger.info(f"Generated {len(df)} samples")
    logger.info(f"Class distribution:\n{df['Label'].value_counts()}")
    
    return df


if __name__ == "__main__":
    # Create data directory
    data_dir = Path("./backend/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate synthetic data
    df = generate_synthetic_data(n_samples=10000)
    
    # Save to CSV
    output_path = data_dir / "synthetic_traffic_data.csv"
    df.to_csv(output_path, index=False)
    logger.info(f"Data saved to {output_path}")
    
    print(f"\n✓ Synthetic training data generated successfully")
    print(f"  File: {output_path}")
    print(f"  Samples: {len(df)}")
    print(f"  Features: {len(df.columns) - 1}")
    print(f"  Classes: {df['Label'].nunique()}")

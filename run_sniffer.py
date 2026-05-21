"""
Run Packet Sniffer
Standalone script to run the packet sniffer for testing
"""

import sys
import time
import argparse
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.capture_engine.packet_sniffer import get_sniffer
from backend.flow_engine.flow_builder import get_flow_builder
from backend.feature_engine.feature_extractor import get_feature_extractor
from backend.detection_engine.model_loader import get_model_loader
from backend.detection_engine.predictor import get_predictor
from backend.alert_engine.alert_manager import get_alert_manager
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run IDS Packet Sniffer")
    parser.add_argument("--interface", type=str, default="eth0", help="Network interface")
    parser.add_argument("--filter", type=str, default="ip", help="BPF filter")
    parser.add_argument("--model", type=str, default="ensemble", help="Model to load")
    parser.add_argument("--duration", type=int, default=60, help="Run duration in seconds")
    args = parser.parse_args()
    
    # Initialize components
    logger.info("Initializing IDS components...")
    
    # Load model
    model_loader = get_model_loader()
    if not model_loader.load_from_directory(args.model):
        logger.error(f"Failed to load model: {args.model}")
        logger.info("Please train a model first using: python backend/ml/training.py")
        return
    
    # Initialize predictor
    predictor = get_predictor(model_loader=model_loader)
    
    # Initialize alert manager
    alert_manager = get_alert_manager()
    
    # Initialize flow builder
    flow_builder = get_flow_builder()
    
    # Initialize feature extractor
    feature_extractor = get_feature_extractor()
    
    # Initialize sniffer
    sniffer = get_sniffer(interface=args.interface, filter_expr=args.filter)
    
    # Packet callback
    def packet_callback(packet_info):
        """Process captured packet"""
        # Add to flow builder
        flow = flow_builder.add_packet(packet_info)
        
        if flow and flow.packet_count >= 10:  # Only process flows with enough packets
            try:
                # Predict
                prediction = predictor.predict_flow(flow)
                
                # Generate alert if attack
                if predictor.is_attack(prediction):
                    alert = alert_manager.generate_alert(
                        prediction,
                        flow.get_stats()
                    )
                    if alert:
                        logger.warning(f"ALERT: {alert['attack_type']} from {alert['src_ip']} (severity: {alert['severity']})")
            except Exception as e:
                logger.error(f"Error processing flow: {e}")
    
    # Set callback
    sniffer.callback = packet_callback
    
    # Start sniffer
    logger.info(f"Starting sniffer on interface {args.interface}")
    sniffer.start()
    
    try:
        # Run for specified duration
        logger.info(f"Running for {args.duration} seconds...")
        time.sleep(args.duration)
        
        # Print statistics
        logger.info("\n=== Statistics ===")
        logger.info(f"Sniffer: {sniffer.get_stats()}")
        logger.info(f"Flows: {flow_builder.get_stats()}")
        logger.info(f"Predictor: {predictor.get_stats()}")
        logger.info(f"Alert Manager: {alert_manager.get_stats()}")
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        # Stop sniffer
        sniffer.stop()
        logger.info("Sniffer stopped")


if __name__ == "__main__":
    main()

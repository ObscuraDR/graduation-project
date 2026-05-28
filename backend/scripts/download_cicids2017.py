"""
Download CICIDS2017 Dataset
============================
3 phương pháp download, tự động thử từng cách.

Usage:
    python backend/scripts/download_cicids2017.py

Yêu cầu (chọn 1):
    pip install huggingface_hub     (Cách 1 — khuyến nghị)
    pip install kaggle              (Cách 2 — cần API key)
    Trình duyệt                     (Cách 3 — thủ công)

Output:
    backend/data/cicids2017/*.csv

Sau khi download:
    python backend/scripts/preprocess_cicids2017.py --input-dir backend/data/cicids2017 --output backend/data/cicids2017_processed.csv
    python backend/ml/train_flow_model.py --data backend/data/cicids2017_processed.csv --model ensemble
"""

import sys
from pathlib import Path

OUTPUT_DIR = Path("backend/data/cicids2017")


def method_1_huggingface():
    """
    Cách 1: Hugging Face Hub (khuyến nghị)
    Cài: pip install huggingface_hub
    Không cần đăng ký, không cần API key.
    """
    print("\n[Method 1] Hugging Face Hub")
    print("-" * 40)

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("  huggingface_hub chưa cài. Chạy:")
        print("  pip install huggingface_hub")
        return False

    print("  Downloading from: bencorn/CICIDS2017")
    print(f"  Output: {OUTPUT_DIR.absolute()}")
    print("  (Có thể mất 10-30 phút tùy tốc độ mạng...)\n")

    try:
        snapshot_download(
            repo_id="bencorn/CICIDS2017",
            repo_type="dataset",
            local_dir=str(OUTPUT_DIR),
            ignore_patterns=["*.md", ".gitattributes"],
        )
        print("\n  ✅ Download thành công!")
        return True
    except Exception as e:
        print(f"\n  ❌ Lỗi: {e}")
        return False


def method_2_kaggle():
    """
    Cách 2: Kaggle API
    Cài: pip install kaggle
    Cần: ~/.kaggle/kaggle.json (API key từ kaggle.com/settings)
    """
    print("\n[Method 2] Kaggle API")
    print("-" * 40)

    try:
        import kaggle
    except (ImportError, OSError):
        print("  kaggle chưa cài hoặc chưa có API key.")
        print("  Cài: pip install kaggle")
        print("  API key: https://www.kaggle.com/settings → Create New Token")
        print("  Lưu vào: ~/.kaggle/kaggle.json")
        return False

    print("  Downloading from: cicdataset/cicids2017")
    print(f"  Output: {OUTPUT_DIR.absolute()}")

    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        api.dataset_download_files(
            "cicdataset/cicids2017",
            path=str(OUTPUT_DIR),
            unzip=True,
        )
        print("\n  ✅ Download thành công!")
        return True
    except Exception as e:
        print(f"\n  ❌ Lỗi: {e}")
        return False


def method_3_manual():
    """
    Cách 3: Download thủ công (luôn hoạt động)
    """
    print("\n[Method 3] Download thủ công")
    print("-" * 40)
    print()
    print("  Chọn MỘT trong các nguồn sau:")
    print()
    print("  📥 Nguồn 1: Kaggle (nhanh nhất, ~300MB zip)")
    print("     1. Mở: https://www.kaggle.com/datasets/cicdataset/cicids2017")
    print("     2. Click 'Download' (cần Kaggle account miễn phí)")
    print("     3. Giải nén vào: backend/data/cicids2017/")
    print()
    print("  📥 Nguồn 2: UNB Official")
    print("     1. Mở: https://www.unb.ca/cic/datasets/ids-2017.html")
    print("     2. Scroll xuống → Download 'MachineLearningCSV.zip'")
    print("     3. Giải nén vào: backend/data/cicids2017/")
    print()
    print("  📥 Nguồn 3: Google Drive (search)")
    print("     1. Google: 'CICIDS2017 MachineLearningCSV google drive download'")
    print("     2. Download zip file")
    print("     3. Giải nén vào: backend/data/cicids2017/")
    print()
    print("  Sau khi giải nén, thư mục phải chứa các file:")
    print("    - Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv")
    print("    - Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv")
    print("    - Friday-WorkingHours-Morning.pcap_ISCX.csv")
    print("    - Monday-WorkingHours.pcap_ISCX.csv")
    print("    - Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv")
    print("    - Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv")
    print("    - Tuesday-WorkingHours.pcap_ISCX.csv")
    print("    - Wednesday-workingHours.pcap_ISCX.csv")
    print()
    return False


def verify_download():
    """Kiểm tra xem download đã thành công chưa."""
    csv_files = list(OUTPUT_DIR.glob("*.csv"))
    # Bỏ qua dummy_data.csv
    real_files = [f for f in csv_files if f.name != "dummy_data.csv"]

    if len(real_files) >= 4:
        total_size = sum(f.stat().st_size for f in real_files)
        print(f"\n{'='*60}")
        print(f"✅ CICIDS2017 dataset ready!")
        print(f"   Files: {len(real_files)} CSV files")
        print(f"   Size: {total_size / 1024 / 1024:.1f} MB")
        print(f"   Location: {OUTPUT_DIR.absolute()}")
        print(f"\n   Next steps:")
        print(f"   python backend/scripts/preprocess_cicids2017.py \\")
        print(f"     --input-dir backend/data/cicids2017 \\")
        print(f"     --output backend/data/cicids2017_processed.csv")
        print(f"{'='*60}")
        return True
    return False


def main():
    print("=" * 60)
    print("CICIDS2017 Dataset Downloader")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Kiểm tra đã có chưa
    if verify_download():
        print("\nDataset đã có sẵn. Không cần download lại.")
        return

    # Thử từng method
    if method_1_huggingface():
        verify_download()
        return

    if method_2_kaggle():
        verify_download()
        return

    # Fallback: hướng dẫn thủ công
    method_3_manual()

    print(f"\n{'='*60}")
    print("Sau khi download thủ công, chạy lại script này để verify:")
    print(f"  python backend/scripts/download_cicids2017.py")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

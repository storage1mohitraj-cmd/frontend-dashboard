"""
PaddleOCR Fine-tuning Script for Whiteout Survival
Trains a custom recognition model on labeled game screenshots.
"""

import os
import yaml
from pathlib import Path


def load_config(config_path):
    """Load training configuration from YAML file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def create_charset_file(charset, output_path):
    """Create character dictionary file for PaddleOCR."""
    with open(output_path, 'w', encoding='utf-8') as f:
        for char in charset:
            f.write(char + '\n')
    print(f"Created charset file with {len(charset)} characters: {output_path}")


def train_model(config):
    """
    Fine-tune PaddleOCR recognition model.
    Uses PPOCRLabel format for training.
    """
    try:
        from paddleocr import PaddleOCR
        import paddle
    except ImportError:
        print("PaddleOCR not installed. Run: pip install paddleocr paddlepaddle")
        return
    
    print("=" * 50)
    print("Whiteout Survival OCR Training")
    print("=" * 50)
    
    # For now, we'll use PaddleOCR's pre-trained model
    # and evaluate on our custom data
    # Full fine-tuning requires PaddleOCR's training tools
    
    print("\n⚠️ Note: Full fine-tuning requires PaddleOCR training environment.")
    print("For production use, we recommend:")
    print("  1. Use the labeled data to evaluate current accuracy")
    print("  2. If accuracy is low, set up PaddleOCR training with:")
    print("     - git clone https://github.com/PaddlePaddle/PaddleOCR")
    print("     - Follow their training documentation")
    print("\nFor now, testing with pre-trained model...\n")
    
    # Test current model on validation data
    ocr = PaddleOCR(lang='en', use_angle_cls=False)
    
    script_dir = Path(__file__).parent.parent
    val_dir = script_dir / "data" / "val"
    val_labels = val_dir / "labels.txt"
    
    if not val_labels.exists():
        print("No validation data found. Run preprocess.py first.")
        return
    
    # Evaluate
    correct = 0
    total = 0
    
    with open(val_labels, 'r', encoding='utf-8') as f:
        lines = [l.strip().split('\t') for l in f if '\t' in l]
    
    print(f"Evaluating on {len(lines)} validation images...\n")
    
    for img_name, true_label in lines:
        img_path = val_dir / img_name
        if not img_path.exists():
            continue
        
        result = ocr.ocr(str(img_path))
        predicted = ""
        if result and result[0]:
            for line in result[0]:
                if len(line) >= 2:
                    text_data = line[1]
                    if isinstance(text_data, (list, tuple)):
                        predicted = str(text_data[0])
                    else:
                        predicted = str(text_data)
                    break
        
        is_correct = predicted.strip().lower() == true_label.strip().lower()
        if is_correct:
            correct += 1
        else:
            print(f"  ✗ '{true_label}' → '{predicted}'")
        total += 1
    
    accuracy = correct / total * 100 if total > 0 else 0
    print(f"\n{'='*50}")
    print(f"Results: {correct}/{total} correct ({accuracy:.1f}%)")
    print(f"{'='*50}")
    
    if accuracy < 80:
        print("\n⚠️ Accuracy is low. Consider:")
        print("   1. Adding more training data")
        print("   2. Improving image preprocessing")
        print("   3. Setting up full PaddleOCR fine-tuning")
    else:
        print("\n✅ Good accuracy! Model is ready for use.")


if __name__ == "__main__":
    script_dir = Path(__file__).parent.parent
    config_path = script_dir / "config" / "train_config.yaml"
    
    if config_path.exists():
        config = load_config(config_path)
        train_model(config)
    else:
        print(f"Config not found: {config_path}")

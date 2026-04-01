#!/usr/bin/env python3
"""
Test script to verify that the packages are setup correctly.
"""

import sys
import os

# Add the ai-reviewer-ml directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ai-reviewer-ml'))

# Test that we can import the modules
try:
    from ai_reviewer_ml.cli import MLCLI
    print("SUCCESS: Successfully imported MLCLI from ai_reviewer_ml.cli")

    # Test model imports
    from ai_reviewer_ml.models import CritiqueModel, SummarizationModel, TerminologyModel, ClassificationModel
    print("SUCCESS: Successfully imported all model modules")

    # Show what models are available
    print("Available models:")
    print("- CritiqueModel")
    print("- SummarizationModel")
    print("- TerminologyModel")
    print("- ClassificationModel")

    # Test help functionality
    cli = MLCLI()
    print("SUCCESS: Created MLCLI instance")

except ImportError as e:
    print(f"ERROR: Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: Other error occurred: {e}")
    sys.exit(1)

print("Package setup verification completed successfully!")
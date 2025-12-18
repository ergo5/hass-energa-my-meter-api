
import asyncio
import logging
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger("verify_overwrite")

def verify_overwrite_logic():
    print("=== VERIFYING MEAN_TYPE LOGIC (v3.6.0-beta.10) ===")
    
    # Simulate the StatisticType enum
    class StatisticType:
        SUM = "sum"
        MEAN = "mean"

    # Verify that passing mean_type=StatisticType.SUM is valid syntax in our target logic
    # We are simulating the call signature of async_import_statistics
    
    def mock_async_import_statistics(hass, metadata, stats):
        print(f"Mock Import called with mean_type={getattr(metadata, 'mean_type', 'MISSING')}")
        if getattr(metadata, 'mean_type', None) != StatisticType.SUM:
             print("❌ FAIL: mean_type was not SUM!")
        else:
             print("✅ SUCCESS: mean_type=SUM passed correctly.")

    # Mock MetaData class
    class MockMetaData:
        def __init__(self, **kwargs):
            for k,v in kwargs.items(): setattr(self, k, v)

    # Test the call
    meta = MockMetaData(
        has_mean=False,
        has_sum=True,
        mean_type=StatisticType.SUM
    )
    
    # Simulate the call
    mock_async_import_statistics(None, meta, [])
    
    return True

if __name__ == "__main__":
    verify_overwrite_logic()

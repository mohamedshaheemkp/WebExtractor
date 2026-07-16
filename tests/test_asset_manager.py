from webextractor.core.asset_manager import AssetManager
from webextractor.models.asset import Asset
from webextractor.models.asset import AssetType


manager = AssetManager()

asset = Asset(
    url="https://example.com/style.css",
    original_url="https://example.com/style.css",
    domain="example.com",
    path="/style.css",
    filename="style.css",
    extension="css",
    asset_type=AssetType.CSS,
)

manager.add(asset)
manager.add(asset)

assert manager.count == 1

print(manager.statistics())
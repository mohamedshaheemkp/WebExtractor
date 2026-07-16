from webextractor.core.mirror import Mirror
from webextractor.models.asset import Asset
from webextractor.models.asset import AssetType


mirror = Mirror()

asset = Asset(
    url="https://example.com/css/style.css?v=10",
    original_url="https://example.com/css/style.css?v=10",
    domain="example.com",
    path="/css/style.css",
    filename="style.css",
    extension="css",
    asset_type=AssetType.CSS,
)

mirror.prepare(asset)

print(asset.local_path)
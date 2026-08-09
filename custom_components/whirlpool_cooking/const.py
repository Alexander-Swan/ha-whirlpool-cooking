"""Constants for Whirlpool Cooking."""

from __future__ import annotations

DOMAIN = "whirlpool_cooking"

CONF_BRAND = "brand"
CONF_REGION = "region"

BRAND_WHIRLPOOL = "whirlpool"
BRAND_KITCHENAID = "kitchenaid"
BRAND_MAYTAG = "maytag"
BRAND_CONSUL = "consul"

REGION_US = "US"
REGION_EU = "EU"

BRANDS = [
    BRAND_WHIRLPOOL,
    BRAND_KITCHENAID,
    BRAND_MAYTAG,
    BRAND_CONSUL,
]

REGIONS = [
    REGION_US,
    REGION_EU,
]

PLATFORMS = ["binary_sensor", "button", "sensor"]

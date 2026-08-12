"""Constants for Whirlpool Cooking."""

from __future__ import annotations

DOMAIN = "whirlpool_cooking"

CONF_BRAND = "brand"
CONF_REGION = "region"
CONF_TEMPERATURE_UNIT = "temperature_unit"

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

TEMP_UNIT_CELSIUS = "celsius"
TEMP_UNIT_FAHRENHEIT = "fahrenheit"

TEMP_UNITS = [
    TEMP_UNIT_CELSIUS,
    TEMP_UNIT_FAHRENHEIT,
]

PLATFORMS = [
    "binary_sensor",
    "button",
    "fan",
    "light",
    "number",
    "select",
    "sensor",
    "switch",
    "text",
]

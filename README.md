# Whirlpool Cooking

Custom Home Assistant integration for Whirlpool-family cooking appliances that are
not fully covered by Home Assistant Core's Whirlpool integration.

The first goal is cloud-backed read-only support for ovens, ranges, wall ovens,
combination ovens, and microwaves registered in the official Whirlpool,
KitchenAid, Maytag, or compatible app. Local control is intentionally tracked as a
research milestone until the appliance LAN protocol is confirmed.

## Status

This project is an early test integration. The current implementation focuses on:

- UI configuration by account, region, and brand
- discovery of cooking appliances from Whirlpool's unofficial 6th Sense API
- read-only entities for appliance state, mode, target temperature, time
  remaining, door state, and connectivity
- a manual refresh diagnostic button
- diagnostics that help identify unsupported oven and microwave data models

Heating controls will be added only when the API payloads are confirmed for real
devices.

## Installation

### Manual test install

Copy the integration directory into your Home Assistant config directory:

```text
custom_components/whirlpool_cooking -> /config/custom_components/whirlpool_cooking
```

Then restart Home Assistant and add `Whirlpool Cooking` from
Settings > Devices & services.

### HACS custom repository

1. Add this repository to HACS as a custom repository.
   `https://github.com/Alexander-Swan/ha-whirlpool-cooking`
2. Select category `Integration`.
3. Download the integration.
4. Restart Home Assistant.
5. Add `Whirlpool Cooking` from Settings > Devices & services.

## Supported brands

- Whirlpool
- KitchenAid
- Maytag
- Consul

## Known limitations

- The integration is cloud polling only.
- Entity mappings are based on expected Whirlpool library attributes and still
  need validation against real cooking appliance payloads.
- No heating, mode, timer, or temperature controls are exposed yet.
- If setup succeeds but entities are empty or unavailable, download diagnostics
  from the device entry and open an issue with the sanitized output.

## Development

Home Assistant currently requires Python 3.14.2 or newer for a full development
environment. Older local Python versions can still run the static tests, but the
Home Assistant runtime tests will be skipped.

```powershell
python -m pip install -r requirements_test.txt
python -m pytest
```

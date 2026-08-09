# Whirlpool Cooking for Home Assistant

Custom HACS integration for Whirlpool-family cooking appliances that are not fully
covered by Home Assistant Core's Whirlpool integration.

The first goal is cloud-backed support for ovens, ranges, wall ovens, combination
ovens, and microwaves registered in the official Whirlpool, KitchenAid, Maytag, or
compatible app. Local control is intentionally tracked as a research milestone until
the appliance LAN protocol is confirmed.

## Status

This project is an early scaffold. The initial implementation focuses on:

- UI configuration by account, region, and brand
- discovery of cooking appliances from Whirlpool's unofficial 6th Sense API
- read-only entities for appliance/cavity state
- diagnostics that help identify unsupported oven and microwave data models

Heating controls will be added only when the API payloads are confirmed for real
devices.

## Installation

1. Add this repository to HACS as a custom repository.
2. Select category `Integration`.
3. Download the integration.
4. Restart Home Assistant.
5. Add `Whirlpool Cooking` from Settings > Devices & services.

## Supported brands

- Whirlpool
- KitchenAid
- Maytag
- Consul

## Development

Home Assistant currently requires Python 3.14.2 or newer for a full development
environment. Older local Python versions can still run the static tests, but the
Home Assistant runtime tests will be skipped.

```powershell
python -m pip install -r requirements_test.txt
python -m pytest
```

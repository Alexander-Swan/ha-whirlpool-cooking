# Whirlpool Cooking

![Whirlpool Cooking icon](custom_components/whirlpool_cooking/brand/icon.png)

Custom Home Assistant integration for Whirlpool-family cooking appliances that
are not fully covered by Home Assistant Core's Whirlpool integration.

The integration talks to Whirlpool's cloud API through
`whirlpool-sixth-sense` and creates Home Assistant devices and entities for
ovens, ranges, wall ovens, combination ovens, and microwaves registered in the
official Whirlpool, KitchenAid, Maytag, or compatible app.

## Status

This project is an early test integration. The current implementation supports:

- UI configuration by account, region, brand, and temperature display unit
- discovery of Whirlpool cooking appliances from the unofficial 6th Sense API
- push-style attribute updates when the library connection is available, with a
  polling fallback if push setup fails
- oven cavity devices and entities for state, temperature, door, light, cook
  mode, target temperature, and cook start/stop controls
- kitchen timer duration, start, and cancel controls when timer operation
  attributes are reported by the appliance
- microwave sensors plus hood light, microwave light, and multi-speed hood fan
  controls when those attributes are reported by the appliance
- global appliance sensors, switches, diagnostics, and a manual refresh button

Entity coverage depends on the attributes exposed by each appliance model. If a
model does not report a backing Whirlpool attribute, the matching entity is not
created.

## Devices

Each physical Whirlpool appliance is represented as one Home Assistant device
unless it exposes more than one oven cavity.

| Appliance shape | Device layout |
| --- | --- |
| Single-cavity oven or range | One device using the appliance name, with cavity entities attached to that device. |
| Double oven or two-cavity range | Separate child devices named with the appliance name plus `Upper` and `Lower`. Cavity entities are attached to the matching child device. |
| Microwave or microwave hood combo | One device using the appliance name. Microwave, hood light, and hood fan entities are attached to that device. |

For a two-cavity appliance, the integration should not also create a generic
`Oven` child device for cavity entities.

## Exposed Entities

### All Appliances

| Platform | Entity | Notes |
| --- | --- | --- |
| `binary_sensor` | Online | Connectivity state from `get_online()`. |
| `button` | Refresh | Diagnostic button that requests a fresh cloud update. |
| `text` | Kitchen timer duration | Created when the appliance reports `KitchenTimer01_SetTimeSet` and supports timer commands. Accepts values like `10:00`, `1:30:00`, `90`, or `1h 30m`. |
| `button` | Start kitchen timer | Starts the kitchen timer using the configured duration. |
| `button` | Cancel kitchen timer | Cancels the kitchen timer. |
| `switch` | Control lock | Created when `Sys_OperationSetControlLock` is present. |
| `switch` | Sabbath mode | Created when `Sys_OperationSetSabbathModeEnabled` is present. |

### Oven Cavities

The following entities are created per existing cavity. On a double oven these
appear under the `Upper` and `Lower` child devices; on a single-cavity oven they
stay on the main appliance device.

| Platform | Entity | Notes |
| --- | --- | --- |
| `sensor` | State | Current cavity state. |
| `sensor` | Mode | Current cook mode. |
| `sensor` | Temperature | Current cavity temperature, displayed as Celsius or Fahrenheit based on the integration option. |
| `sensor` | Target temperature | Current target temperature, displayed as Celsius or Fahrenheit based on the integration option. |
| `sensor` | Cook time | Configured cook time when available, otherwise elapsed cook time. Displayed as `M:SS` or `H:MM:SS`. |
| `sensor` | Cook time remaining | Created when the cavity reports remaining cook time. Displayed as `M:SS` or `H:MM:SS`. |
| `sensor` | Delay time remaining | Created when the cavity reports delay time. Displayed as `M:SS` or `H:MM:SS`. |
| `sensor` | Recipe cook time | Created when the cavity reports recipe cook time. Displayed as `M:SS` or `H:MM:SS`. |
| `sensor` | Recipe temperature | Created when the cavity reports recipe display temperature. |
| `sensor` | Recipe mode | Created when the cavity reports recipe mode. |
| `binary_sensor` | Door | Door open state. |
| `binary_sensor` | Door locked | Created when the cavity reports door lock state. |
| `light` | Light | Created when the cavity reports a light status attribute. |
| `select` | Cook mode | Selects a supported cook mode for the cavity. Options are filtered from appliance capability data when available. |
| `number` | Target temperature | Sets the pending target temperature for the cavity in the configured display unit. |
| `button` | Start cook | Starts cooking using the current or pending cook mode and target temperature. |
| `button` | Stop cook | Stops cooking for the cavity. |

### Microwave And Hood

Microwave entities are created from the raw attributes reported by the appliance.

| Platform | Entity | Notes |
| --- | --- | --- |
| `sensor` | State | Microwave cycle or status state when present. |
| `sensor` | Mode | Microwave cook or cycle mode when present. |
| `sensor` | Cook time | Cook duration when present. Displayed as `M:SS` or `H:MM:SS`. |
| `sensor` | Time remaining | Remaining cook duration when present. Displayed as `M:SS` or `H:MM:SS`. |
| `sensor` | Temperature | Display/status temperature when present. |
| `sensor` | Target temperature | Target/set temperature when present. |
| `light` | Microwave light | On/off microwave cavity light when `Mwo_DisplaySetLightOn` is present. |
| `light` | Hood light | Brightness-capable hood surface light when `Hood_OperationSetSurfaceLight` is present. The raw Whirlpool levels are mapped to Home Assistant brightness. |
| `fan` | Hood fan | Multi-speed hood exhaust fan when `Hood_OperationSetExhaustFanSpeed` is present. The raw Whirlpool speeds are exposed as `Low`, `Medium`, `Medium-high`, and `High` preset modes, plus `Off` in the hood fan mode select. |

### Additional Sensors

The integration also creates these sensors when their raw attributes are present:

| Entity | Source attributes |
| --- | --- |
| Kitchen timer time | `KitchenTimer01_SetTimeSet` |
| Kitchen timer time remaining | `KitchenTimer01_StatusTimeRemaining` |
| Kitchen timer state | `KitchenTimer01_StatusState` |
| Fault code | `Sys_AlertStatusCustomerFaultCode` |
| Notification | `Sys_AlertStatusNotification` |
| Customer fault notification | `CustomerFaultCodeNotification` |
| Timezone | `TimeZoneId` |
| UTC offset | `UtcOffset` |
| Date time mode | `DateTimeMode` |
| Appliance version | `ApplianceVersionNumber` |
| Project release | `ProjectReleaseNumber` |
| Model number | `ModelNumber` |
| XCat model number | `XCat_ApplianceInfoSetModelNumber` |
| Real time power | `XCat_PowerStatusRealTimePower` |
| Real time voltage | `XCat_PowerStatusRealTimeVoltage` |
| Real time current | `XCat_PowerStatusRealTimeCurrent` |
| Energy consumption | `XCat_PowerStatusEnergyConsumption` |
| Energy measurement results | `XCat_PowerStatusEnergyMeasurementResults` |
| Power outage | `XCat_PowerStatusPowerOutage` |
| Cycle count | `XCat_OdometerStatusCycleCount` or `Mwo_CycleStatusOdometer` |
| Running hours | `XCat_OdometerStatusRunningHours` |
| Total hours | `XCat_OdometerStatusTotalHours` |
| Wi-Fi RSSI | `XCat_WifiStatusRssiAntennaDiversity` or `WifiRssi` |

## Controls

Oven cooking is controlled from the cavity entities:

1. Pick a value in the cavity `Cook mode` select.
2. Set the cavity `Target temperature` number.
3. Press the cavity `Start cook` button.
4. Press the cavity `Stop cook` button to stop that cavity.

The integration also registers `whirlpool_cooking.set_cook` and
`whirlpool_cooking.stop_cook` services for automation use. Service temperatures
are currently passed in Celsius.

Hood light and hood fan controls use normal Home Assistant `light` and `fan`
services. The hood light supports two Whirlpool brightness levels, and the hood
fan supports `Off`, `Low`, `Medium`, `Medium-high`, and `High` controls.

Kitchen timer control is available when the appliance exposes the Whirlpool
kitchen timer operation attributes. Set `Kitchen timer duration`, then press
`Start kitchen timer`. Use `Cancel kitchen timer` to stop it. The duration text
accepts seconds, `M:SS`, `H:MM:SS`, or compact values like `1h 30m`.

## Options

The integration options include a temperature display unit:

- Celsius
- Fahrenheit

Temperature sensors and number controls use the selected unit in Home Assistant.
Commands sent to Whirlpool are converted back to the Celsius-based values
expected by the library.

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Go to Integrations.
3. Open the three-dot menu and choose Custom repositories.
4. Add this repository URL:

```text
https://github.com/Alexander-Swan/ha-whirlpool-cooking
```

5. Set the category to Integration.
6. Select Add.
7. Search HACS for `Whirlpool Cooking`.
8. Download the integration.
9. Restart Home Assistant.
10. Go to Settings > Devices & services.
11. Select Add Integration and choose `Whirlpool Cooking`.
12. Sign in with your Whirlpool-family account, then choose the matching brand,
    region, and temperature display unit.

If the integration loads but a device exposes fewer entities than expected,
download diagnostics from the Whirlpool Cooking device entry and include the
sanitized output when opening an issue. Entity creation is based on the
attributes and command APIs reported by each appliance.

HACS updates are published from versioned GitHub releases. Install or update the
latest release from HACS unless you intentionally choose a pre-release.

This repository follows the HACS integration publishing layout: one integration
under `custom_components/whirlpool_cooking`, a root `hacs.json`, a versioned
`manifest.json`, and integration brand assets under
`custom_components/whirlpool_cooking/brand/`.

### Versioning

The integration version is stored in
`custom_components/whirlpool_cooking/manifest.json` and mirrored in
`pyproject.toml`.

To prepare a release:

```text
python scripts/set_version.py 0.2.0
```

Commit the version change, then run the `Release` GitHub Actions workflow with
the same version. The workflow validates the checked-in version, runs tests,
creates the `v0.2.0` tag, and publishes the GitHub release used by HACS.

### Manual Test Install

Copy the integration directory into your Home Assistant config directory:

```text
custom_components/whirlpool_cooking -> /config/custom_components/whirlpool_cooking
```

Then restart Home Assistant and add `Whirlpool Cooking` from
Settings > Devices & services.

## Supported Brands

- Whirlpool
- KitchenAid
- Maytag
- Consul

## Known Limitations

- This integration depends on Whirlpool's cloud API and the unofficial
  `whirlpool-sixth-sense` library.
- Entity mappings are based on observed and expected Whirlpool appliance
  attributes. Different models may expose different entities.
- Push updates are used when the library can connect successfully. The
  integration falls back to polling if push setup fails.
- Some controls may be rejected by Whirlpool depending on appliance state,
  remote-control permissions, door state, or regional/model capability.
- If setup succeeds but entities are empty or unavailable, download diagnostics
  from the device entry and open an issue with the sanitized output.

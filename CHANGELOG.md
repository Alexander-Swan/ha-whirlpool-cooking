# Changelog

## 0.2.1

- Fixes kitchen timer and oven cook-duration updates so successful sends refresh
  the local entity state immediately.
- Allows `0` as a timer duration to clear cook timers and rejects unsupported
  duration text instead of partially parsing it.

## 0.2.0

- Adds oven cavity controls for cook mode, target temperature, start/stop, and
  post-preheat timed cook duration.
- Adds microwave hood light and multi-speed hood fan controls.
- Adds kitchen timer duration, start, and cancel controls.
- Adds HACS publishing metadata, validation, and release workflow support.

## 0.1.0

- Initial HACS-ready test release for Whirlpool-family cooking appliances.
- Adds appliance discovery, oven cavity entities, microwave hood controls, and
  kitchen timer controls when supported by the Whirlpool API.

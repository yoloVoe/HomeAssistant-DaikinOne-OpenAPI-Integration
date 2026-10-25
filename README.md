# Daikin One+

This integration connects Home Assistant to Daikin One+ thermostats through
Daikin's cloud API. It supports one thermostat per config entry, reads its state
every three minutes, and provides climate and schedule controls.

## Installing with HACS

This repository is laid out as a HACS custom integration under
`custom_components/daikin_one_plus`. Add the GitHub repository in HACS as a
custom repository with the **Integration** category, install Daikin One+, and
restart Home Assistant.

The custom integration uses the same `daikin_one_plus` domain as the built-in
Home Assistant integration. It replaces that integration and must not be
installed alongside another copy of the domain.

## Setup and authentication

The config flow asks for:

- **API key**: the developer API key, sent in the `x-api-key` HTTP header.
- **Email**: the case-sensitive email address used by the SkyportHome account.
- **API token**: the Integrator Token requested through the app; it is sent as
  `integratorToken` when exchanging credentials for an access token.

Leading and trailing whitespace is removed from each field before the
credentials are validated and saved.

### What Home Assistant persists

On successful setup, the config flow creates a Home Assistant config entry.
Its `data` contains the trimmed API key, email, and Integrator Token. The
thermostat ID returned by Daikin is saved as the config entry's unique ID, so
Home Assistant can find that same thermostat on later startups even if the API
returns devices in a different order. Home Assistant manages persistence of
the config entry in its internal storage (normally
`.storage/core.config_entries`); the integration does not create its own
credentials file or database.

The short-lived Daikin access token is **not persisted**. It exists only in the
in-memory `DaikinApi` client while Home Assistant is running. When the
integration starts again, it exchanges the saved API key, email, and
Integrator Token for a new access token.

### Access-token refresh

The token endpoint returns the access token and its lifetime in seconds. The
client caches the token in memory and considers it expired 30 seconds before
the reported expiry time, so the next API request obtains a fresh one. If a
thermostat request receives HTTP 401, the client invalidates that token,
requests a new one, and retries the request once. It does not retry
authentication failures indefinitely.

During setup, Home Assistant fetches the account's device list and associates
the config entry with the selected thermostat's device ID. The thermostat's
state request is then used for the initial data-coordinator refresh. The
account's first thermostat is selected when initially configuring the entry;
subsequent setup looks up the saved unique ID.

## Entities

The integration creates entities associated with one Home Assistant device:

- **Climate**: current indoor temperature, heat/cool setpoints, and HVAC mode.
  Setpoint changes send both values with the current mode because Daikin's API
  requires all three fields.
- **Schedule switch**: enables or disables the thermostat schedule.
- **Sensors**: indoor humidity, outdoor temperature and humidity, minimum
  setpoint difference, equipment status, mode limit, fan mode, fan circulation,
  and fan circulation speed. Numeric API codes are shown as received where the
  documentation does not provide display labels in the integration.
- **Diagnostic binary sensors**: emergency-heat availability, emergency-heat
  active state, and geofencing enabled state.

Daikin's documented `mode` values are `0=Off`, `1=Heat`, `2=Cool`, `3=Auto`,
and `4=Emergency heat`. Home Assistant has no dedicated emergency-heat climate
mode: mode `4` is represented as Heat by the climate entity, while the
diagnostic emergency-heat-active binary sensor distinguishes it from mode `1`.
When a user selects Heat in Home Assistant, the integration sends Daikin mode
`1`.

Successful manual mode or setpoint updates disable Daikin's schedule and
geofencing. The coordinator reflects these documented side effects immediately
instead of immediately polling again.

## Polling and updates

- At initial setup, the integration fetches thermostat state once to populate
  the coordinator before creating entities.
- During normal operation, the coordinator polls thermostat state every three
  minutes. All read-only entities use this same response; they do not make
  separate requests.
- When a user changes a setpoint, HVAC mode, or schedule, the integration sends
  one corresponding `PUT` request. After a successful response, the coordinator
  updates its in-memory state optimistically so entities reflect the requested
  change without waiting for another GET.
- A successful write does **not** trigger an immediate status GET, a second
  verification request, or more frequent polling. Normal three-minute polling
  continues; the next GET occurs on the coordinator's regular schedule.
- Daikin asks clients to wait at least 15 seconds after a write before polling.
  The integration avoids an immediate post-write GET and therefore respects
  that restriction.

## Home Assistant terminology

- A **config flow** is the UI-driven setup form. On success, its config entry
  persists the long-lived credentials and the thermostat's unique ID.
- An **integration** connects Home Assistant to a service or device protocol.
- A **platform** creates a kind of entity. This integration forwards its config
  entry to the climate, switch, sensor, and binary sensor platforms.
- An **entity** represents one capability or reading, such as the thermostat's
  climate controls or its outdoor temperature.
- A **device** groups related entities that belong to the same physical
  thermostat.
- A **DataUpdateCoordinator** fetches shared state on a schedule and notifies
  all coordinator-based entities when that state changes. Here, a single
  three-minute poll supplies every read-only entity.
- **Runtime data** is in-memory state associated with a config entry. Here it
  holds the coordinator and API client; access tokens are not persisted there
  across Home Assistant restarts.

## Config-entry and platform setup

The integration's manifest declares the domain as `daikin_one_plus`. When the
user submits the config flow, `config_flow.py` validates the credentials,
stores them in a config entry, and saves the thermostat ID as that entry's
unique ID.

When Home Assistant sets up the entry, it calls `async_setup_entry` in
`__init__.py`. That function creates the API client and coordinator, performs
the initial state refresh, stores the coordinator in `entry.runtime_data`, and
forwards setup to the `climate`, `switch`, `sensor`, and `binary_sensor`
platforms.

Home Assistant locates each platform by combining the integration's Python
package path with its platform name. For this integration, `sensor` resolves
to `homeassistant.components.daikin_one_plus.sensor`, or
`homeassistant/components/daikin_one_plus/sensor.py` in the Core source tree.
The same convention maps the other platform names to `climate.py`, `switch.py`,
and `binary_sensor.py` in that directory. Each platform's own
`async_setup_entry` creates its entities and registers them with Home Assistant
through the `async_add_entities` callback.

## Files

| File | Purpose |
| --- | --- |
| `__init__.py` | Creates the API client and coordinator, finds the configured thermostat, and loads/unloads entity platforms. |
| `api.py` | Implements Daikin HTTP requests, access-token lifecycle, response types, and API errors. |
| `binary_sensor.py` | Creates diagnostic boolean entities for emergency heat and geofencing. |
| `climate.py` | Implements climate state, Daikin/Home Assistant mode mapping, and setpoint control. |
| `config_flow.py` | Collects and trims credentials, tests API access, and creates the config entry. |
| `const.py` | Defines the integration domain and Daikin API URLs. |
| `coordinator.py` | Polls thermostat state and distributes it to entities; reflects successful writes optimistically. |
| `manifest.json` | Declares integration metadata used by Home Assistant. |
| `quality_scale.yaml` | Tracks implementation status against Home Assistant's Integration Quality Scale. |
| `sensor.py` | Creates measurement and diagnostic sensor entities. |
| `strings.json` | Source translations for config-flow errors and entity names. |
| `translations/en.json` | Generated English translations loaded by Home Assistant. |

## References

- [Daikin One Open API documentation](https://www.daikinone.com/openapi/documentation/index.html)
- [Daikin One Open API examples](https://www.daikinone.com/openapi/examples/index.html)
- [Home Assistant config flows](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- [Home Assistant data update coordinator](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Home Assistant entity model](https://developers.home-assistant.io/docs/core/entity/)
- [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)

## Tests

Integration tests are in `tests/components/daikin_one_plus/` in the Home
Assistant Core repository. Run them from the repository root with:

```bash
uv run --no-sync pytest -q tests/components/daikin_one_plus
```
